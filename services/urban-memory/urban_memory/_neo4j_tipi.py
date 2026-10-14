"""Protocol condivisi per il sottoinsieme del driver Neo4j usato da Urban Memory.

UNA sola definizione (prima erano copiate in cinque moduli). Ricalcano la
firma ESATTA di neo4j 6.x (vedi il pin in `pyproject.toml`): `Driver.session`
ha parametri keyword-only e `Session.__exit__` ha tre parametri fissi. Una
major nuova del driver può romperli: va riverificato con mypy.

Sono `Protocol` (non i tipi concreti) cosi' i test passano driver finti.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Protocol, TypeVar


class Result(Protocol):
    """Sottoinsieme di `neo4j.Result`: `.data()` e `.single()`."""

    def data(self) -> list[dict[str, Any]]: ...

    def single(self) -> Any: ...


class ReadSession(Protocol):
    """Sessione di sola lettura: `.run(...)` e context manager."""

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> Result: ...

    def __enter__(self) -> ReadSession: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...


class WriteSession(ReadSession, Protocol):
    """Sessione che oltre a `.run` espone `.execute_write` (usata da `graph_link`)."""

    def execute_write(self, transaction_function: Any, *args: Any, **kwargs: Any) -> Any: ...

    def __enter__(self) -> WriteSession: ...


S_co = TypeVar("S_co", covariant=True)


class Driver(Protocol[S_co]):
    """Sottoinsieme di `neo4j.Driver`: `.session(database=...)` e `.close()`."""

    def session(self, *, database: str | None = None) -> S_co: ...

    def close(self) -> None: ...
