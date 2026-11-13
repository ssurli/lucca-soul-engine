# Avvia la demo: build web dell'app + BFF che la serve sulla stessa origine.
# Da eseguire dalla radice del repo (PowerShell 5.1):
#   powershell -ExecutionPolicy Bypass -File scripts\avvia_demo.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\avvia_demo.ps1 -Rete
# Il BFF usa il .env reale (Aura/Neon): lo script va lanciato dall'utente.
# Dopo l'avvio fa UNA sola lettura del grafo (POST /itinerary/adapt con itinerario
# vuoto: nessuna scrittura) e dice se il grafo risponde. Un grafo che non risponde
# (503) e' un AVVISO, non ferma la demo: l'app mostra l'errore in modo gestito.
# Il BFF resta in esecuzione finche' non premi Ctrl+C.
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

# 7. Avvio del BFF (Ctrl+C per fermarlo). Non in primo piano: serve poter
# controllare il grafo dopo l'avvio.
$argomenti = @("-m", "uvicorn", "api.main:app", "--app-dir", "services\api", "--host", $bindHost, "--port", "8000")
$proc = Start-Process -FilePath $python -ArgumentList $argomenti -NoNewWindow -PassThru
$null = $proc.Handle   # PS 5.1: senza leggere Handle subito, ExitCode resta vuoto

try {
    # 8. Attesa di /health (al massimo ~30 s).
    $pronto = $false
    for ($i = 0; $i -lt 30; $i++) {
        if ($proc.HasExited) {
            throw "uvicorn e' terminato prima di rispondere (exit $($proc.ExitCode))."
        }
        try {
            $r = Invoke-WebRequest "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 2
            if ($r.StatusCode -eq 200) { $pronto = $true; break }
        }
        catch { }
        Start-Sleep -Seconds 1
    }
    if (-not $pronto) {
        throw "Il BFF non risponde su /health dopo 30 secondi."
    }

    # 9. Una sola lettura del grafo, senza scritture (niente /itinerary, /memory, /events, /booking).
    $verifica = @'
import json, sys, urllib.error, urllib.request
corpo = {
    "itinerary": {"person_id": "verifica-avvio", "stops": [], "generated_at": "2026-12-12T09:00:00Z"},
    "signal": {"meteo": "sereno", "data": "2026-12-12", "ora": "10:00:00", "affollamento": {}, "stanchezza": 0},
}
req = urllib.request.Request(
    "http://127.0.0.1:8000/itinerary/adapt",
    data=json.dumps(corpo).encode("utf-8"),
    headers={"Content-Type": "application/json; charset=utf-8"},
    method="POST",
)
try:
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=60) as r:
        sys.exit(0 if r.status == 200 else 1)
except urllib.error.HTTPError as e:
    print(e.code)
    sys.exit(3 if e.code == 503 else 1)
except Exception as e:
    print(type(e).__name__)
    sys.exit(1)
'@
    $fileVerifica = Join-Path $env:TEMP "lucca_verifica_grafo.py"
    Set-Content -Path $fileVerifica -Value $verifica -Encoding UTF8
    & $python $fileVerifica
    $esitoVerifica = $LASTEXITCODE
    Remove-Item -Path $fileVerifica -Force -ErrorAction SilentlyContinue
    if ($esitoVerifica -eq 0) {
        Write-Host "Grafo raggiungibile"
    }
    elseif ($esitoVerifica -eq 3) {
        Write-Warning "ATTENZIONE: il grafo non risponde (503). La demo parte lo stesso."
    }
    else {
        Write-Warning "Verifica del grafo non riuscita (codice $esitoVerifica): controlla i messaggi sopra."
    }

    # 10. Il BFF resta attivo fino a Ctrl+C.
    $proc.WaitForExit()
    if ($proc.ExitCode -ne 0) { throw "uvicorn terminato con errore (exit $($proc.ExitCode))." }
}
finally {
    if ($fileVerifica) { Remove-Item -Path $fileVerifica -Force -ErrorAction SilentlyContinue }
    if (-not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    }
}
