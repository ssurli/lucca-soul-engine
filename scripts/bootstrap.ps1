# Lucca Soul Lab - bootstrap Wave 0
# MODALITA CLOUD, ZERO INFRASTRUTTURA LOCALE: Neo4j Aura + Neon (con pgvector).
# Nessun Docker richiesto.
#
# Uso:   .\scripts\bootstrap.ps1
# Se Windows blocca lo script:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "==> Lucca Soul Lab - bootstrap" -ForegroundColor Cyan

# 1. .env
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "==> creato .env da .env.example - compilalo e rilancia." -ForegroundColor Yellow
    exit 0
}

# 2. Carica il .env
$env_vars = @{}
Get-Content ".env" | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { return }
    $i = $line.IndexOf("=")
    if ($i -lt 1) { return }
    $k = $line.Substring(0, $i).Trim()
    $v = $line.Substring($i + 1).Trim().Trim('"').Trim("'")
    $env_vars[$k] = $v
}

# 3. Variabili obbligatorie
$missing = $false
foreach ($v in @("NEO4J_URI","NEO4J_USERNAME","NEO4J_PASSWORD","DATABASE_URL","ANTHROPIC_API_KEY")) {
    $val = $env_vars[$v]
    $isPlaceholder = ($val -match "xxxx") -or ($val -match "ROLE:PASSWORD") -or ($val -match "DBNAME")
    if ([string]::IsNullOrWhiteSpace($val) -or $isPlaceholder) {
        Write-Host "  [X] $v non impostata (o ancora col placeholder)" -ForegroundColor Red
        $missing = $true
    } else {
        Write-Host "  [OK] $v" -ForegroundColor Green
    }
}
if ($missing) { Write-Host "==> Compila le variabili mancanti nel .env e rilancia." -ForegroundColor Yellow; exit 1 }

# 4. Rileva il profilo dal .env (cloud vs locale) e valida di conseguenza
$isLocal = ($env_vars["NEO4J_URI"] -like "bolt://*") -or ($env_vars["DATABASE_URL"] -match "localhost")
if ($isLocal) {
    Write-Host "==> PROFILO LOCALE rilevato (Docker: Neo4j Community + Postgres/pgvector)" -ForegroundColor Cyan
    try { docker compose version | Out-Null } catch {
        Write-Host "  [X] Il .env punta a localhost ma 'docker compose' non e disponibile." -ForegroundColor Red
        Write-Host "      Avvia Docker Desktop, oppure usa il profilo cloud (.env con Aura+Neon)." -ForegroundColor Red
        exit 1
    }
    Write-Host "==> avvio i servizi locali..."
    docker compose up -d
    Write-Host "    attendo che siano sani..."
    Start-Sleep -Seconds 12
} else {
    Write-Host "==> PROFILO CLOUD rilevato (Neo4j Aura + Neon)" -ForegroundColor Cyan
    if (-not ($env_vars["NEO4J_URI"] -like "neo4j+s://*" -or $env_vars["NEO4J_URI"] -like "neo4j+ssc://*")) {
        Write-Host "  [!] Con Aura NEO4J_URI deve essere neo4j+s:// (TLS)." -ForegroundColor Red; exit 1
    }
    if (-not ($env_vars["DATABASE_URL"] -match "sslmode=require")) {
        Write-Host "  [!] DATABASE_URL senza sslmode=require - Neon rifiutera la connessione." -ForegroundColor Red; exit 1
    }
    if ($env_vars["DATABASE_URL"] -match "-pooler\.") {
        Write-Host "  [!] DATABASE_URL e la stringa POOLED. Per migrazioni e seed serve la DIRETTA." -ForegroundColor Yellow
    }
}

# 5. Scheletro cartelle
$dirs = @(
  "apps/lucca_soul_app",
  "services/api","services/experience-engine","services/graph/cypher",
  "services/rag","services/recommender",
  "services/urban-memory","services/intelligence-index",
  "packages/contracts","tests"
)
foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
    if (-not (Get-ChildItem $d -Force | Where-Object { $_.Name -ne ".gitkeep" })) {
        New-Item -ItemType File -Force -Path (Join-Path $d ".gitkeep") | Out-Null
    }
}
Write-Host "==> scheletro cartelle pronto" -ForegroundColor Green

# 6. Verifica connessioni remote + abilita pgvector
foreach ($k in $env_vars.Keys) { [Environment]::SetEnvironmentVariable($k, $env_vars[$k], "Process") }

$py = @"
import os, sys
ok = True

try:
    from neo4j import GraphDatabase
    d = GraphDatabase.driver(os.environ['NEO4J_URI'],
        auth=(os.environ['NEO4J_USERNAME'], os.environ['NEO4J_PASSWORD']))
    d.verify_connectivity(); d.close()
    print('  [OK] Neo4j Aura raggiungibile')
except ModuleNotFoundError:
    print('  (check Neo4j saltato: pip install neo4j)')
except Exception as e:
    print(f'  [X] Neo4j Aura: {e}'); ok = False

try:
    import psycopg
    with psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=15, autocommit=True) as c:
        c.execute('SELECT 1')
        print('  [OK] Neon Postgres raggiungibile')
        c.execute('CREATE EXTENSION IF NOT EXISTS vector')
        r = c.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()
        if r:
            print(f'  [OK] pgvector abilitato (v{r[0]}) - nessun Qdrant, nessun Docker')
        else:
            print('  [X] pgvector non risulta abilitato'); ok = False
except ModuleNotFoundError:
    print('  (check Postgres saltato: pip install "psycopg[binary]")')
except Exception as e:
    print(f'  [X] Neon Postgres: {e}'); ok = False

sys.exit(0 if ok else 2)
"@
try { $py | python - } catch { Write-Host "  (verifica remota saltata: python non trovato)" -ForegroundColor Yellow }

Write-Host ""
Write-Host "==> Bootstrap completo." -ForegroundColor Cyan
if ($isLocal) {
    Write-Host "    PROFILO LOCALE (Docker)"
    Write-Host "    Neo4j        -> http://localhost:7474  (bolt: 7687)"
    Write-Host "    Postgres     -> localhost:5432"
    Write-Host "    Vector store -> pgvector, nello stesso Postgres"
} else {
    Write-Host "    PROFILO CLOUD"
    Write-Host "    Neo4j        -> Aura (neo4j+s://)"
    Write-Host "    Postgres     -> Neon (sslmode=require)"
    Write-Host "    Vector store -> pgvector, dentro Neon"
    Write-Host ""
    Write-Host "[!] Aura Free: l'istanza e CANCELLATA dopo 30 giorni di inattivita." -ForegroundColor Yellow
    Write-Host "    Il seed del grafo e versionato e ricreabile in un comando." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Prossimo passo: apri Claude Code nel repo e segui RUNBOOK.md."
