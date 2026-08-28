<#
.SYNOPSIS
  Avvia PostgreSQL (se non gia' attivo) e il backend leank-spc.
  Da rilanciare a ogni riavvio del PC o dopo stop.ps1 - nulla parte
  automaticamente da solo (nessun servizio Windows registrato).
#>

. "$PSScriptRoot\common.ps1"

if (-not (Test-Path (Get-PgCtlExe))) {
    Write-Host "PostgreSQL non risulta installato. Eseguire prima installer\install.ps1" -ForegroundColor Red
    exit 1
}

Write-Step "PostgreSQL"
if (Test-PostgresRunning) {
    Write-Ok "Gia' in esecuzione"
} else {
    $logFile = Join-Path $LogsDir "postgres.log"
    # niente "| Write-Host": postgres.exe resta attivo ed eredita l'handle di
    # stdout, altrimenti PowerShell resta in attesa di un EOF che non arriva
    # mai finche' il server non si ferma (vedi stessa nota in install.ps1)
    & (Get-PgCtlExe) start -D $PgDataDir -l $logFile -o "-p $PgPort -c listen_addresses=127.0.0.1" -w
    Write-Ok "Avviato"
}

Write-Step "Backend FastAPI"
if (Test-BackendRunning) {
    Write-Ok "Gia' in esecuzione su http://127.0.0.1:$BackendPort"
} else {
    $backendDir = Join-Path $ProjectRoot "backend"
    $pidFile = Join-Path $RuntimeDir "backend.pid"
    $logFile = Join-Path $LogsDir "backend.log"

    $process = Start-Process -FilePath (Get-PythonExe) `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort" `
        -WorkingDirectory $backendDir `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError (Join-Path $LogsDir "backend.err.log") `
        -WindowStyle Hidden `
        -PassThru

    $process.Id | Set-Content $pidFile
    Write-Ok "Avviato (PID $($process.Id)), log in $logFile"

    Write-Host "   Attendo che risponda..."
    $ready = $false
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Seconds 1
        if (Test-BackendRunning) { $ready = $true; break }
    }
    if (-not $ready) {
        Write-WarnStep "Il backend non ha risposto entro 20s - controllare $logFile"
    }
}

Write-Host ""
Write-Host "Backend pronto: http://127.0.0.1:$BackendPort/docs" -ForegroundColor Green
Write-Host "(Swagger UI - utile per provare le API senza scrivere codice)"
