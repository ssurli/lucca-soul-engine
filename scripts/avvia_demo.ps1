# Avvia la demo: build web dell'app + BFF che la serve sulla stessa origine.
# Da eseguire dalla radice del repo (PowerShell 5.1):
#   powershell -ExecutionPolicy Bypass -File scripts\avvia_demo.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\avvia_demo.ps1 -Rete
# Il BFF usa il .env reale (Aura/Neon): lo script va lanciato dall'utente.
param(
    [string]$Istante = "2026-12-12T09:00:00Z",
    [switch]$Rete
)

# Niente $ErrorActionPreference = "Stop": in PS 5.1 lo stderr dei comandi nativi
# (flutter, uvicorn) diventerebbe un errore terminante. Ogni passo nativo e'
# seguito da un controllo esplicito di $LASTEXITCODE.

# 1. Istante: SOLO forma yyyy-MM-ddTHH:mm:ssZ.
if ($Istante -notmatch '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$') {
    throw "Istante non valido: '$Istante'. Usa solo la forma con Z, ad esempio 2026-12-12T09:00:00Z"
}
$parsed = [DateTime]::MinValue
$ok = [DateTime]::TryParseExact(
    $Istante, "yyyy-MM-ddTHH:mm:ssZ",
    [Globalization.CultureInfo]::InvariantCulture,
    [Globalization.DateTimeStyles]::AdjustToUniversal -bor [Globalization.DateTimeStyles]::AssumeUniversal,
    [ref]$parsed)
if (-not $ok) {
    throw "Istante non valido: '$Istante' non e' una data/ora reale. Esempio: 2026-12-12T09:00:00Z"
}
$istantePomeriggio = $parsed.AddHours(5).ToString("yyyy-MM-ddTHH:mm:ssZ", [Globalization.CultureInfo]::InvariantCulture)

# 2. Radice del repo = cartella corrente (controllo).
$radice = (Get-Location).Path
$python = Join-Path $radice ".venv\Scripts\python.exe"
$cartellaApp = Join-Path $radice "apps\lucca_soul_app"
if (-not (Test-Path $python)) {
    throw "Non trovo .venv\Scripts\python.exe: esegui lo script dalla radice del repo, dopo il bootstrap."
}
if (-not (Test-Path $cartellaApp)) {
    throw "Non trovo la cartella dell'app ($cartellaApp): esegui lo script dalla radice del repo."
}

# 3. Flutter presente?
if (-not (Get-Command flutter -ErrorAction SilentlyContinue)) {
    throw "Il comando 'flutter' non esiste: installa Flutter e aggiungilo al PATH, poi rilancia."
}

# 4. Porta 8000 libera?
$occupata = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($occupata) {
    $pidOccupante = ($occupata | Select-Object -First 1).OwningProcess
    throw ("La porta 8000 e' occupata dal processo con PID $pidOccupante. " +
        "Per liberarla esegui: Stop-Process -Id $pidOccupante   " +
        "(poi rilancia lo script).")
}

# 5. Build web dell'app.
Push-Location $cartellaApp
try {
    flutter build web --release --no-web-resources-cdn --dart-define=DEMO=true "--dart-define=DEMO_ISTANTE=$Istante"
    if ($LASTEXITCODE -ne 0) { throw "flutter build web fallita (exit $LASTEXITCODE)." }
}
finally {
    Pop-Location
}

$buildWeb = Join-Path $cartellaApp "build\web"
if (-not (Test-Path (Join-Path $buildWeb "index.html"))) {
    throw "La build non ha prodotto $buildWeb\index.html."
}
$env:APP_WEB_DIR = $buildWeb

# 6. Indirizzi del copione.
$bindHost = "127.0.0.1"
if ($Rete) { $bindHost = "0.0.0.0" }

Write-Host ""
Write-Host "Indirizzi della demo:"
Write-Host "  Mattina   (10:00 a Lucca): http://localhost:8000/"
Write-Host "  Pomeriggio (15:00)       : http://localhost:8000/?istante=$istantePomeriggio"
if ($Rete) {
    $ipv4 = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
        Select-Object -ExpandProperty IPAddress
    foreach ($ip in $ipv4) {
        Write-Host "  Da rete: http://${ip}:8000/"
        Write-Host "  Da rete: http://${ip}:8000/?istante=$istantePomeriggio"
    }
    Write-Warning ("Modalita' -Rete: SOLO per la demo su rete fidata. " +
        "POST /memory e POST /booking scrivono su Neon e /docs e' leggibile da chiunque sulla rete.")
}
Write-Host ""

# 7. Avvio del BFF (Ctrl+C per fermarlo).
& $python -m uvicorn api.main:app --app-dir services\api --host $bindHost --port 8000
if ($LASTEXITCODE -ne 0) { throw "uvicorn terminato con errore (exit $LASTEXITCODE)." }
