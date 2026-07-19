"""Fixture condivise per i test del Recommender.

Include un cluster Postgres 16 EFFIMERO (usa e getta) per testare
`PostgresBehaviorEventRepository` contro un database VERO — stesso
protocollo di Neon (un DSN `postgresql://...`), solo locale: stesso pattern
di `services/marketplace/tests/conftest.py` (a sua volta ricalcato su
`services/urban-memory/tests/conftest.py`). Se i binari Postgres 16 (o i
permessi per avviarli) non sono disponibili in questo ambiente, i test che
dipendono da `postgres_cluster` sono saltati con `pytest.skip` — non
falliscono. Versione CORRETTA per Windows: `pwd` (Unix-only) è importato
SOLO dentro il ramo che lo usa, mai a livello di modulo — un import a
livello di modulo romperebbe la sola collection della suite su Windows.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import tempfile
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import psycopg
import pytest

# ---------------------------------------------------------------------------
# Postgres effimero — un cluster reale (initdb + pg_ctl), non un mock.
# ---------------------------------------------------------------------------


def _find_pg_bin_dir() -> Path | None:
    """Cerca `initdb` in posizioni note (Debian/Ubuntu: `/usr/lib/postgresql/
    <versione>/bin`) o nel `PATH`. `None` se Postgres non è installato."""
    candidati: list[Path] = [Path("/usr/lib/postgresql/16/bin")]
    base = Path("/usr/lib/postgresql")
    if base.is_dir():
        for sotto in sorted(base.iterdir(), reverse=True):
            candidati.append(sotto / "bin")
    for candidato in candidati:
        if (candidato / "initdb").exists():
            return candidato
    trovato = shutil.which("initdb")
    if trovato:
        return Path(trovato).resolve().parent
    return None


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@dataclass
class _EphemeralPostgres:
    """Un cluster Postgres 16 avviato per la sessione di test, ascolto su
    TCP `127.0.0.1:<porta libera>`, auth `trust` (solo locale, usa e getta:
    mai un pattern da riusare per un ambiente reale)."""

    base_dir: Path
    port: int
    bin_dir: Path
    run_as: str | None  # utente OS per `sudo -u` (serve solo se pytest gira come root)

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    def _argv(self, executable: str, *args: str) -> list[str]:
        eseguibile = str(self.bin_dir / executable)
        if self.run_as:
            return ["sudo", "-u", self.run_as, eseguibile, *args]
        return [eseguibile, *args]

    def _run(self, executable: str, *args: str) -> None:
        risultato = subprocess.run(
            self._argv(executable, *args), capture_output=True, text=True, timeout=60
        )
        if risultato.returncode != 0:
            raise RuntimeError(
                f"{executable} fallito (rc={risultato.returncode}):\n"
                f"stdout: {risultato.stdout}\nstderr: {risultato.stderr}"
            )

    def admin_dsn(self, dbname: str = "postgres") -> str:
        return f"postgresql://postgres@127.0.0.1:{self.port}/{dbname}"

    def stop(self) -> None:
        try:
            self._run("pg_ctl", "stop", "-D", str(self.data_dir), "-m", "fast", "-w")
        except RuntimeError:
            pass  # best-effort: si pulisce comunque la directory
        shutil.rmtree(self.base_dir, ignore_errors=True)


def _start_ephemeral_postgres() -> _EphemeralPostgres | None:
    """`None` se questo ambiente non può avviare un Postgres effimero
    (binari assenti, o pytest gira come root senza un utente `postgres`/
    `sudo` per delegargli l'avvio — Postgres rifiuta di girare come root)."""
    bin_dir = _find_pg_bin_dir()
    if bin_dir is None:
        return None

    run_as: str | None = None
    tmp_base = tempfile.gettempdir()
    # `os.geteuid` non esiste su Windows: questo intero ramo (delega a un
    # utente di sistema "postgres" via sudo) è rilevante solo su un
    # container Linux/CI eseguito come root, dove Postgres si rifiuta di
    # girare come root. `pwd` è Unix-only: import locale, mai a livello di
    # modulo, altrimenti la sola collection del conftest crasha su Windows.
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        import pwd

        try:
            pwd.getpwnam("postgres")
        except KeyError:
            return None
        if shutil.which("sudo") is None:
            return None
        run_as = "postgres"
        tmp_base = "/tmp"

    base_dir = Path(tempfile.mkdtemp(prefix="recommender_pgtest_", dir=tmp_base))
    if run_as:
        import pwd

        utente = pwd.getpwnam(run_as)
        os.chown(base_dir, utente.pw_uid, utente.pw_gid)
    os.chmod(base_dir, 0o700)

    cluster = _EphemeralPostgres(
        base_dir=base_dir, port=_free_tcp_port(), bin_dir=bin_dir, run_as=run_as
    )

    try:
        cluster._run("initdb", "-D", str(cluster.data_dir), "--auth=trust", "--username=postgres")
        log_path = base_dir / "pg.log"
        cluster._run(
            "pg_ctl",
            "start",
            "-D",
            str(cluster.data_dir),
            "-l",
            str(log_path),
            "-w",
            "-t",
            "30",
            "-o",
            f"-p {cluster.port} -c listen_addresses=127.0.0.1 "
            f"-c unix_socket_directories={base_dir}",
        )
    except (RuntimeError, OSError):
        shutil.rmtree(base_dir, ignore_errors=True)
        return None

    return cluster


@pytest.fixture(scope="session")
def postgres_cluster() -> Iterator[_EphemeralPostgres]:
    """Cluster Postgres 16 EFFIMERO condiviso dall'intera sessione di test.
    Salta (`pytest.skip`) tutti i test che lo richiedono se questo ambiente
    non può avviarlo — non li fa fallire."""
    cluster = _start_ephemeral_postgres()
    if cluster is None:
        pytest.skip(
            "Postgres 16 non disponibile in questo ambiente (binari assenti "
            "o permessi insufficienti per avviarlo): test di persistenza "
            "reale saltati, non falliti."
        )
    try:
        yield cluster
    finally:
        cluster.stop()


@pytest.fixture
def pg_dsn(postgres_cluster: _EphemeralPostgres) -> Iterator[str]:
    """Un `DATABASE_URL` isolato per il singolo test: crea un database
    dedicato sul cluster effimero condiviso e lo elimina a fine test."""
    nome_db = f"recommender_test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(postgres_cluster.admin_dsn(), autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{nome_db}"')
    dsn = postgres_cluster.admin_dsn(nome_db)
    try:
        yield dsn
    finally:
        with psycopg.connect(postgres_cluster.admin_dsn(), autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{nome_db}" WITH (FORCE)')


@pytest.fixture
def pg_repo(pg_dsn: str):
    """`PostgresBehaviorEventRepository` già migrata, pronta all'uso."""
    from recommender.migrate import migrate
    from recommender.repository import PostgresBehaviorEventRepository

    migrate(pg_dsn)
    return PostgresBehaviorEventRepository(pg_dsn)


@pytest.fixture(params=["in_memory", "postgres"])
def any_behavior_event_repository(request: pytest.FixtureRequest):
    """Parametrizza gli stessi test sul `Protocol BehaviorEventRepository`
    contro ENTRAMBE le implementazioni: se un test passa solo su una, la
    seconda lo segnala. Il ramo `postgres` richiede il cluster effimero:
    salta (non fallisce) se non disponibile, tramite `pg_dsn`."""
    if request.param == "in_memory":
        from recommender.repository import InMemoryBehaviorEventRepository

        return InMemoryBehaviorEventRepository()

    dsn = request.getfixturevalue("pg_dsn")
    from recommender.migrate import migrate
    from recommender.repository import PostgresBehaviorEventRepository

    migrate(dsn)
    return PostgresBehaviorEventRepository(dsn)
