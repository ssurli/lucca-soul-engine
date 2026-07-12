#!/usr/bin/env bash
# Lucca Soul — bootstrap Wave 0.
# Crea lo scheletro delle cartelle, prepara .env e avvia l'infrastruttura dati.
# Idempotente: rieseguibile senza danni.
set -euo pipefail

cd "$(dirname "$0")/.."
echo "==> Lucca Soul bootstrap"

# 1. Prerequisiti
command -v docker >/dev/null 2>&1 || { echo "ERRORE: docker non trovato."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "ERRORE: 'docker compose' (v2) non disponibile."; exit 1; }

# 2. .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> creato .env da .env.example (ricordati di mettere ANTHROPIC_API_KEY)"
else
  echo "==> .env già presente, lo lascio"
fi

# 3. Scheletro cartelle (come in CLAUDE.md); .gitkeep per versionarle vuote
for d in \
  apps/lucca_soul_app \
  services/api services/experience-engine services/graph/cypher \
  services/rag services/recommender \
  services/urban-memory services/intelligence-index \
  packages/contracts tests ; do
  mkdir -p "$d"
  [ -z "$(ls -A "$d" 2>/dev/null)" ] && touch "$d/.gitkeep"
done
echo "==> scheletro cartelle pronto"

# 4. Infrastruttura dati
echo "==> avvio Postgres, Neo4j, Qdrant..."
docker compose up -d

# 5. Attesa health
echo "==> attendo che i servizi siano sani..."
for i in $(seq 1 30); do
  pg=$(docker inspect -f '{{.State.Health.Status}}' lucca_postgres 2>/dev/null || echo "n/a")
  neo=$(docker inspect -f '{{.State.Health.Status}}' lucca_neo4j 2>/dev/null || echo "n/a")
  if [ "$pg" = "healthy" ] && [ "$neo" = "healthy" ]; then
    echo "==> Postgres e Neo4j sani."
    break
  fi
  sleep 3
done

# 6. Riepilogo
cat <<'MSG'

==> Bootstrap completo.
    Postgres  -> localhost:5432
    Neo4j     -> http://localhost:7474  (bolt: 7687)
    Qdrant    -> http://localhost:6333

Prossimo passo: apri Claude Code nel repo e segui RUNBOOK.md.
Per fermare l'infrastruttura:  docker compose down   (aggiungi -v per cancellare i dati)
MSG
