# Lucca Soul Lab - bootstrap Wave 0 (MODALITA CLOUD: Aura + Neon + Qdrant locale)
# Versione PowerShell (Windows). Equivalente a scripts/bootstrap.sh.
# Uso:   .\scripts\bootstrap.ps1
# Se Windows blocca lo script:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")
Write-Host "==> Lucca Soul Lab - bootstrap (cloud)" -ForegroundColor Cyan

# 1. Prerequisiti
try { docker --version | Out-Null } catch { Write-Host "ERRORE: docker non trovato." -ForegroundColor Red; exit 1 }
try { docker compose version | Out-Null } catch { Write-Host "ERRORE: 'docker compose' v2 non disponibile." -ForegroundColor Red; exit 1 }

# 2. .env
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "==> creato .env da .env.example - compilalo e rilancia." -ForegroundColor Yellow
    exit 0
}

# 3. Carica il .env (gestisce virgolette e commenti)
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

# 4. Variabili obbligatorie
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

# 5. Trappole classiche
if ($env_vars["NEO4J_URI"] -like "bolt://*") {
    Write-Host "  [!] NEO4J_URI usa bolt:// - con Aura serve neo4j+s:// (TLS). Correggi il .env." -ForegroundColor Red; exit 1
}
if (-not ($env_vars["NEO4J_URI"] -like "neo4j+s://*" -or $env_vars["NEO4J_URI"] -like "neo4j+ssc://*")) {
    Write-Host "  [!] NEO4J_URI ha uno schema inatteso." -ForegroundColor Red; exit 1
}
if (-not ($env_vars["DATABASE_URL"] -match "sslmode=require")) {
    Write-Host "  [!] DATABASE_URL senza sslmode=require - Neon rifiutera la connessione." -ForegroundColor Red; exit 1
}

# 6. Scheletro cartelle
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

# 7. Qdrant
Write-Host "==> avvio Qdrant..."
docker compose up -d
Start-Sleep -Seconds 3
$qurl = if ($env_vars["QDRANT_URL"]) { $env_vars["QDRANT_URL"] } else { "http://localhost:6333" }
try {
    Invoke-WebRequest -Uri $qurl -UseBasicParsing -TimeoutSec 5 | Out-Null
    Write-Host "  [OK] Qdrant risponde" -ForegroundColor Green
} catch {
    Write-Host "  [!] Qdrant non risponde ancora (riprova tra qualche secondo)" -ForegroundColor Yellow
}

# 8. Verifica connessioni remote (richiede: pip install neo4j "psycopg[binary]")
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
    print('  (check saltato: pip install neo4j "psycopg[binary]")'); sys.exit(0)
except Exception as e:
    print(f'  [X] Neo4j Aura: {e}'); ok = False
try:
    import psycopg
    with psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=10) as c:
        c.execute('SELECT 1')
    print('  [OK] Neon Postgres raggiungibile')
except ModuleNotFoundError:
    print('  (check Postgres saltato: pip install "psycopg[binary]")')
except Exception as e:
    print(f'  [X] Neon Postgres: {e}'); ok = False
sys.exit(0 if ok else 2)
"@
foreach ($k in $env_vars.Keys) { [Environment]::SetEnvironmentVariable($k, $env_vars[$k], "Process") }
try { $py | python - } catch { Write-Host "  (verifica remota saltata: python non trovato)" -ForegroundColor Yellow }

Write-Host ""
Write-Host "==> Bootstrap completo." -ForegroundColor Cyan
Write-Host "    Neo4j    -> Aura (cloud, neo4j+s://)"
Write-Host "    Postgres -> Neon (cloud, sslmode=require)"
Write-Host "    Qdrant   -> $qurl"
Write-Host ""
Write-Host "[!] Aura Free: l'istanza va in pausa per inattivita ed e CANCELLATA dopo 30 giorni" -ForegroundColor Yellow
Write-Host "    senza attivita. Il seed del grafo resta versionato in services/graph/cypher/ -" -ForegroundColor Yellow
Write-Host "    e ricreabile in ogni momento. Non tenere dati solo su Aura." -ForegroundColor Yellow
Write-Host ""
Write-Host "Prossimo passo: apri Claude Code nel repo e segui RUNBOOK.md."
