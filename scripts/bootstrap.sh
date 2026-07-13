#!/usr/bin/env bash
# Lucca Soul Lab — bootstrap Wave 0
# MODALITÀ CLOUD, ZERO INFRASTRUTTURA LOCALE: Neo4j Aura + Neon (con pgvector).
# Nessun Docker richiesto. (Su Windows PowerShell usa: .\scripts\bootstrap.ps1)
set -euo pipefail
cd "$(dirname "$0")/.."
echo "==> Lucca Soul Lab — bootstrap (cloud, no Docker)"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> creato .env da .env.example — compilalo e rilancia."; exit 0
fi
set -a; . ./.env; set +a

missing=0
for v in NEO4J_URI NEO4J_USERNAME NEO4J_PASSWORD DATABASE_URL ANTHROPIC_API_KEY; do
  if [ -z "${!v:-}" ] || case "${!v}" in *xxxx*|*ROLE:PASSWORD*|*DBNAME*) true;; *) false;; esac; then
    echo "  ✗ $v non impostata (o placeholder)"; missing=1
  else echo "  ✓ $v"; fi
done
[ "$missing" -eq 1 ] && { echo "==> Compila le variabili mancanti nel .env e rilancia."; exit 1; }

case "$NEO4J_URI" in
  neo4j+s://*|neo4j+ssc://*) : ;;
  bolt://*) echo "  ⚠  NEO4J_URI usa bolt:// — con Aura serve neo4j+s:// (TLS)."; exit 1 ;;
  *) echo "  ⚠  NEO4J_URI ha uno schema inatteso."; exit 1 ;;
esac
case "$DATABASE_URL" in
  *sslmode=require*) : ;;
  *) echo "  ⚠  DATABASE_URL senza sslmode=require — Neon rifiuterà la connessione."; exit 1 ;;
esac
case "$DATABASE_URL" in
  *-pooler.*) echo "  ⚠  DATABASE_URL è la stringa POOLED: per migrazioni/seed serve la DIRETTA." ;;
esac

for d in \
  apps/lucca_soul_app \
  services/api services/experience-engine services/graph/cypher \
  services/rag services/recommender \
  services/urban-memory services/intelligence-index \
  packages/contracts tests ; do
  mkdir -p "$d"; [ -z "$(ls -A "$d" 2>/dev/null)" ] && touch "$d/.gitkeep"
done
echo "==> scheletro cartelle pronto"

python3 - <<'PY' || echo "  (verifica remota saltata: pip install neo4j 'psycopg[binary]')"
import os, sys
ok = True
try:
    from neo4j import GraphDatabase
    d = GraphDatabase.driver(os.environ['NEO4J_URI'],
        auth=(os.environ['NEO4J_USERNAME'], os.environ['NEO4J_PASSWORD']))
    d.verify_connectivity(); d.close()
    print('  ✓ Neo4j Aura raggiungibile')
except ModuleNotFoundError:
    raise SystemExit(1)
except Exception as e:
    print(f'  ✗ Neo4j Aura: {e}'); ok = False
try:
    import psycopg
    with psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=15, autocommit=True) as c:
        c.execute('SELECT 1'); print('  ✓ Neon Postgres raggiungibile')
        c.execute('CREATE EXTENSION IF NOT EXISTS vector')
        r = c.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()
        print(f'  ✓ pgvector abilitato (v{r[0]}) — nessun Qdrant, nessun Docker' if r
              else '  ✗ pgvector non abilitato')
        ok = ok and bool(r)
except ModuleNotFoundError:
    raise SystemExit(1)
except Exception as e:
    print(f'  ✗ Neon Postgres: {e}'); ok = False
sys.exit(0 if ok else 2)
PY

cat <<'MSG'

==> Bootstrap completo.
    Neo4j        -> Aura (cloud, neo4j+s://)
    Postgres     -> Neon (cloud, sslmode=require)
    Vector store -> pgvector DENTRO Neon (nessun Docker)

⚠  Aura Free: l'istanza va in pausa e viene CANCELLATA dopo 30 giorni di inattività.
   Il seed del grafo è versionato in services/graph/cypher/ ed è ricreabile in un comando.

Prossimo passo: apri Claude Code nel repo e segui RUNBOOK.md.
MSG
