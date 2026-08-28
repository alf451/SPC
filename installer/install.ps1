<#
.SYNOPSIS
  Installer "pilot mode" per leank-spc: nessun privilegio di amministratore,
  nessun servizio Windows, nessuna modifica al sistema fuori dalla cartella
  del progetto. Pensato per affiancare MeasurLink durante un test sul campo,
  facilmente rimovibile con uninstall.ps1.

.DESCRIPTION
  Scarica Python embeddable e PostgreSQL portable (nessun installer MSI),
  li configura dentro <progetto>\runtime, crea il database e applica le
  migration. Rieseguibile in sicurezza: salta i passi gia' completati.
#>

. "$PSScriptRoot\common.ps1"

Write-Host "=== leank-spc - installazione pilot mode ===" -ForegroundColor Magenta
Write-Host "Cartella progetto: $ProjectRoot"
Write-Host "Cartella runtime:  $RuntimeDir (tutto qui dentro, nulla fuori)"

Assert-Dir $RuntimeDir
Assert-Dir $LogsDir
Assert-Dir $SecretsDir
$downloadsDir = Join-Path $RuntimeDir "downloads"
Assert-Dir $downloadsDir

# -------------------------------------------------------------------------
# 1. Python embeddable (nessuna installazione di sistema)
# -------------------------------------------------------------------------
Write-Step "Python embeddable"
$pythonExe = Get-PythonExe
if (-not (Test-Path $pythonExe)) {
    $zipPath = Join-Path $downloadsDir "python-embed.zip"
    Invoke-DownloadFile -Url $PythonEmbedUrl -Destination $zipPath
    Assert-Dir $PythonDir
    Expand-ZipFile -ZipPath $zipPath -Destination $PythonDir
    Write-Ok "Estratto in $PythonDir"

    # L'embeddable disabilita site-packages/pip per default: lo riabilitiamo.
    $pthFile = Get-ChildItem -Path $PythonDir -Filter "python*._pth" | Select-Object -First 1
    if ($pthFile) {
        (Get-Content $pthFile.FullName) -replace '^#import site', 'import site' | Set-Content $pthFile.FullName
        Add-Content -Path $pthFile.FullName -Value "Lib\site-packages"
        Write-Ok "site-packages abilitato ($($pthFile.Name))"
    } else {
        Write-WarnStep "File _pth non trovato: verificare manualmente l'abilitazione di site-packages"
    }

    $getPipPath = Join-Path $downloadsDir "get-pip.py"
    Invoke-DownloadFile -Url "https://bootstrap.pypa.io/get-pip.py" -Destination $getPipPath
    & $pythonExe $getPipPath --no-warn-script-location | Write-Host
    Assert-LastExitCode "installazione pip"
    Write-Ok "pip installato"
} else {
    Write-Ok "Python gia' pronto in $PythonDir"
}

Write-Step "Dipendenze Python (backend + edge agent)"
& $pythonExe -m pip install --no-warn-script-location -r (Join-Path $ProjectRoot "backend\requirements.txt") | Write-Host
Assert-LastExitCode "pip install backend/requirements.txt"
& $pythonExe -m pip install --no-warn-script-location -r (Join-Path $ProjectRoot "edge-agent\requirements.txt") | Write-Host
Assert-LastExitCode "pip install edge-agent/requirements.txt"
Write-Ok "Dipendenze installate"

# -------------------------------------------------------------------------
# 2. PostgreSQL portable (zip binari, nessun MSI/servizio)
# -------------------------------------------------------------------------
Write-Step "PostgreSQL portable"
$pgCtl = Get-PgCtlExe
if (-not (Test-Path $pgCtl)) {
    $zipPath = Join-Path $downloadsDir "postgresql-binaries.zip"
    Invoke-DownloadFile -Url $PgBinariesUrl -Destination $zipPath
    Assert-Dir $PgDir
    Expand-ZipFile -ZipPath $zipPath -Destination $PgDir
    Write-Ok "Estratto in $PgDir"
} else {
    Write-Ok "PostgreSQL gia' pronto in $PgDir"
}

$pgSuperuserPasswordFile = Join-Path $SecretsDir "pg_superuser_password.txt"
if (-not (Test-Path $pgSuperuserPasswordFile)) {
    New-RandomSecret | Set-Content -NoNewline $pgSuperuserPasswordFile
}
$pgSuperuserPassword = Get-Content $pgSuperuserPasswordFile -Raw

if (-not (Test-Path (Join-Path $PgDataDir "PG_VERSION"))) {
    Write-Step "Inizializzazione data directory PostgreSQL"
    $initdb = Join-Path $PgDir "pgsql\bin\initdb.exe"
    $pwFile = Join-Path $downloadsDir "pg_superuser_pwfile.tmp"
    Set-Content -NoNewline -Path $pwFile -Value $pgSuperuserPassword
    & $initdb -D $PgDataDir -U postgres --pwfile=$pwFile --encoding=UTF8 --auth=trust | Write-Host
    Remove-Item $pwFile
    Write-Ok "Data directory creata in $PgDataDir"
} else {
    Write-Ok "Data directory gia' inizializzata"
}

Write-Step "Avvio PostgreSQL (porta $PgPort, solo localhost)"
if (-not (Test-PostgresRunning)) {
    $logFile = Join-Path $LogsDir "postgres.log"
    # NOTA: niente "| Write-Host" qui. postgres.exe resta in esecuzione dopo che
    # pg_ctl termina ed eredita l'handle di stdout: se lo si mette in pipeline,
    # PowerShell resta in attesa di un EOF che non arriva mai finche' il server
    # non si ferma, con lo script che sembra bloccarsi indefinitamente.
    & $pgCtl start -D $PgDataDir -l $logFile -o "-p $PgPort -c listen_addresses=127.0.0.1" -w
} else {
    Write-Ok "PostgreSQL gia' in esecuzione"
}

Write-Step "Creazione database applicativo"
$psql = Get-PsqlExe
$env:PGPASSWORD = $pgSuperuserPassword
$appPasswordFile = Join-Path $SecretsDir "pg_app_password.txt"
if (-not (Test-Path $appPasswordFile)) {
    New-RandomSecret | Set-Content -NoNewline $appPasswordFile
}
$appPassword = Get-Content $appPasswordFile -Raw

$roleExists = & $psql -h 127.0.0.1 -p $PgPort -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$PgUser'" postgres
if (-not $roleExists -or $roleExists.Trim() -ne "1") {
    & $psql -h 127.0.0.1 -p $PgPort -U postgres -c "CREATE ROLE $PgUser LOGIN PASSWORD '$appPassword';" postgres | Write-Host
}
$dbExists = & $psql -h 127.0.0.1 -p $PgPort -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$PgDbName'" postgres
if (-not $dbExists -or $dbExists.Trim() -ne "1") {
    & $psql -h 127.0.0.1 -p $PgPort -U postgres -c "CREATE DATABASE $PgDbName OWNER $PgUser;" postgres | Write-Host
}
Remove-Item Env:\PGPASSWORD
Write-Ok "Database '$PgDbName' pronto (utente '$PgUser')"

# -------------------------------------------------------------------------
# 3. Configurazione backend (.env) + migration
# -------------------------------------------------------------------------
Write-Step "Configurazione backend"
$envPath = Join-Path $ProjectRoot "backend\.env"
$jwtSecretFile = Join-Path $SecretsDir "jwt_secret.txt"
if (-not (Test-Path $jwtSecretFile)) {
    New-RandomSecret -Length 48 | Set-Content -NoNewline $jwtSecretFile
}
$jwtSecret = Get-Content $jwtSecretFile -Raw

@"
DATABASE_URL=postgresql+asyncpg://${PgUser}:${appPassword}@127.0.0.1:$PgPort/$PgDbName
JWT_SECRET=$jwtSecret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=14
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:8000,null
"@ | Set-Content $envPath
Write-Ok "Scritto $envPath"

Write-Step "Migration database (alembic upgrade head)"
Push-Location (Join-Path $ProjectRoot "backend")
try {
    & $pythonExe -m alembic upgrade head | Write-Host
    Assert-LastExitCode "alembic upgrade head"
    Write-Ok "Schema applicato"
} finally {
    Pop-Location
}

Write-Step "Utente amministratore"
$adminPasswordFile = Join-Path $SecretsDir "admin_password.txt"
if (-not (Test-Path $adminPasswordFile)) {
    New-RandomSecret -Length 16 | Set-Content -NoNewline $adminPasswordFile
}
$adminPassword = Get-Content $adminPasswordFile -Raw
Push-Location (Join-Path $ProjectRoot "backend")
try {
    & $pythonExe create_admin.py admin $adminPassword | Write-Host
    Assert-LastExitCode "create_admin.py"
} finally {
    Pop-Location
}
Write-Ok "Utente 'admin' pronto (password in $adminPasswordFile)"

Write-Host ""
Write-Host "=== Installazione completata ===" -ForegroundColor Magenta
Write-Host "Per avviare il backend:  installer\start.ps1"
Write-Host "Per fermarlo:            installer\stop.ps1"
Write-Host "Per disinstallare tutto: installer\uninstall.ps1"
Write-Host ""
Write-Host "Login iniziale: utente 'admin', password in $adminPasswordFile"
Write-Host "Credenziali PostgreSQL salvate in: $SecretsDir (non versionare, gia' in .gitignore)"
