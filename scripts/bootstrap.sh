#!/usr/bin/env bash
# Lucca Soul Lab — bootstrap Wave 0 (MODALITÀ CLOUD: Aura + Neon + Qdrant locale).
# Crea lo scheletro, avvia Qdrant e VERIFICA le connessioni remote prima di iniziare.
# Idempotente.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "==> Lucca Soul Lab — bootstrap (cloud)"

command -v docker >/dev/null 2>&1 || { echo "ERRORE: docker non trovato."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "ERRORE: 'docker compose' v2 non disponibile."; exit 1; }

# 1. .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> creato .env da .env.example — compilalo e rilancia."
  exit 0
fi
set -a; . ./.env; set +a

# 2. Controllo variabili obbligatorie
missing=0
for v in NEO4J_URI NEO4J_USERNAME NEO4J_PASSWORD DATABASE_URL ANTHROPIC_API_KEY; do
  if [ -z "${!v:-}" ] || case "${!v}" in *xxxx*|*ROLE:PASSWORD*|*DBNAME*|sk-ant-xxx*) true;; *) false;; esac; then
    echo "  ✗ $v non impostata (o ancora col placeholder)"; missing=1
  else
    echo "  ✓ $v"
  fi
done
[ "$missing" -eq 1 ] && { echo "==> Compila le variabili mancanti nel .env e rilancia."; exit 1; }

# 3. Trappola classica: Aura richiede neo4j+s://, non bolt://
case "$NEO4J_URI" in
  neo4j+s://*|neo4j+ssc://*) : ;;
  bolt://*) echo "  ⚠  NEO4J_URI usa bolt:// — con Aura serve neo4j+s:// (TLS). Correggi il .env."; exit 1 ;;
  *) echo "  ⚠  NEO4J_URI ha uno schema inatteso: $NEO4J_URI"; exit 1 ;;
esac
# Neon richiede sslmode=require
case "$DATABASE_URL" in
  *sslmode=require*) : ;;
  *) echo "  ⚠  DATABASE_URL senza sslmode=require — Neon rifiuterà la connessione."; exit 1 ;;
esac

# 4. Scheletro cartelle
for d in \
  apps/lucca_soul_app \
  services/api services/experience-engine services/graph/cypher \
  services/rag services/recommender \
  services/urban-memory services/intelligence-index \
  packages/contracts tests ; do
  mkdir -p "$d"; [ -z "$(ls -A "$d" 2>/dev/null)" ] && touch "$d/.gitkeep"
done
echo "==> scheletro cartelle pronto"

# 5. Qdrant in locale
echo "==> avvio Qdrant..."
docker compose up -d
sleep 3
curl -sf "${QDRANT_URL:-http://localhost:6333}" >/dev/null && echo "  ✓ Qdrant risponde" || echo "  ⚠ Qdrant non risponde ancora (riprova tra qualche secondo)"

# 6. Verifica connessioni remote (se sono disponibili i client Python)
python3 - <<'PY' 2>/dev/null || echo "  (verifica remota saltata: installa 'neo4j' e 'psycopg[binary]' per il check automatico)"
import os, sys
ok = True
try:
    from neo4j import GraphDatabase
    d = GraphDatabase.driver(os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]))
    d.verify_connectivity(); d.close()
    print("  ✓ Neo4j Aura raggiungibile")
except ModuleNotFoundError:
    raise SystemExit(1)
except Exception as e:
    print(f"  ✗ Neo4j Aura: {e}"); ok = False
try:
    import psycopg
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=10) as c:
        c.execute("SELECT 1")
    print("  ✓ Neon Postgres raggiungibile")
except ModuleNotFoundError:
    raise SystemExit(1)
except Exception as e:
    print(f"  ✗ Neon Postgres: {e}"); ok = False
sys.exit(0 if ok else 2)
PY

cat <<'MSG'

==> Bootstrap completo.
    Neo4j    -> Aura (cloud, neo4j+s://)
    Postgres -> Neon (cloud, sslmode=require)
    Qdrant   -> http://localhost:6333

⚠  Aura Free: l'istanza va in pausa per inattività ed è CANCELLATA dopo 30 giorni
   senza attività. Il seed del grafo resta versionato in services/graph/cypher/ —
   è ricreabile in ogni momento. Non tenere dati solo su Aura.

Prossimo passo: apri Claude Code nel repo e segui RUNBOOK.md.
MSG
