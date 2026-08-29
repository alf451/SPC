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

.PARAMETER Port
  Porta su cui ascolta il backend (default 8000). Utile se qualcos'altro
  (IIS, un altro servizio) occupa gia' quella porta su questo PC.

.PARAMETER ExposeNetwork
  Se presente, il backend ascolta su tutte le interfacce (0.0.0.0) invece
  che solo su 127.0.0.1: raggiungibile da altre macchine della rete (es.
  Edge Agent su altre postazioni). Richiede una regola firewall - lo script
  prova a crearla, ma serve una sessione PowerShell da amministratore
  perche' funzioni; altrimenti stampa il comando da lanciare a mano.

.PARAMETER Https
  Se presente, il backend parla HTTPS invece di HTTP. Senza -SslCertFile/
  -SslKeyFile genera da solo un certificato auto-firmato (va bene per una
  LAN fidata - il browser mostrera' un avviso "non attendibile" ma il
  traffico e' comunque cifrato; per un dominio pubblico serve invece un
  certificato vero, vedi docs/installazione.md).

.PARAMETER SslCertFile
  Percorso a un certificato .pem/.crt gia' pronto (richiede anche -SslKeyFile).

.PARAMETER SslKeyFile
  Percorso alla chiave privata corrispondente a -SslCertFile.

.EXAMPLE
  .\install.ps1
  Interattivo: chiede porta, esposizione in rete e HTTPS con Enter per i default.

.EXAMPLE
  .\install.ps1 -Port 8080 -ExposeNetwork -Https
  Non interattivo, certificato auto-firmato generato in automatico.
#>
param(
    [int]$Port = 0,
    [switch]$ExposeNetwork,
    [switch]$Https,
    [string]$SslCertFile = "",
    [string]$SslKeyFile = ""
)

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
# 3. Porta, raggiungibilita' in rete e HTTPS
# -------------------------------------------------------------------------
Write-Step "Porta e raggiungibilita' del backend"
$envPath = Join-Path $ProjectRoot "backend\.env"
$envAlreadyConfigured = (Test-Path $envPath) -and (Get-Content $envPath | Where-Object { $_ -match "^BACKEND_PORT=" })
# Se uno qualunque di questi e' stato passato esplicitamente, si considera la
# chiamata "da script" e non si chiede nulla per nessuno dei tre: o tutto a
# riga di comando, o tutto interattivo (evita di chiedere solo meta' delle cose).
$paramsGivenExplicitly = ($Port -ne 0) -or $ExposeNetwork.IsPresent -or $Https.IsPresent -or ($SslCertFile -ne "")

if ($envAlreadyConfigured -and -not $paramsGivenExplicitly) {
    # Riesecuzione dello script senza parametri: rispetta la scelta gia' fatta
    $backendPort = [int](Get-BackendPort)
    $backendHost = Get-BackendHost
    $sslCertPath = Get-EnvValue -Key "BACKEND_SSL_CERTFILE" -Default ""
    $sslKeyPath = Get-EnvValue -Key "BACKEND_SSL_KEYFILE" -Default ""
    $scheme = if ($sslCertPath) { "https" } else { "http" }
    Write-Ok "Configurazione gia' presente: $scheme`://$backendHost`:$backendPort (invariata)"
} else {
    $interactive = [Environment]::UserInteractive -and -not $paramsGivenExplicitly

    if ($interactive) {
        $answer = Read-Host "Porta del backend [invio per $BackendPortDefault]"
        $backendPort = if ($answer) { [int]$answer } else { $BackendPortDefault }
    } else {
        $backendPort = if ($Port -ne 0) { $Port } else { $BackendPortDefault }
    }
    if (Test-PortInUse -Port $backendPort) {
        Write-WarnStep "La porta $backendPort risulta gia' in uso da un altro programma (es. IIS) - scegline un'altra."
    }

    if ($interactive) {
        $answer = Read-Host "Raggiungibile anche da altre macchine della rete, non solo da questo PC? [s/N]"
        $ExposeNetwork = $answer -match '^[sS]'
    }
    $backendHost = if ($ExposeNetwork) { "0.0.0.0" } else { "127.0.0.1" }
    Write-Ok "Backend su $backendHost`:$backendPort"

    if ($interactive -and -not $Https.IsPresent) {
        $answer = Read-Host "Usare HTTPS invece di HTTP? [s/N]"
        $Https = $answer -match '^[sS]'
    }

    $sslCertPath = ""
    $sslKeyPath = ""
    if ($Https -or $SslCertFile -ne "") {
        if ($SslCertFile -ne "") {
            if (-not (Test-Path $SslCertFile) -or -not (Test-Path $SslKeyFile)) {
                throw "Certificato o chiave non trovati: $SslCertFile / $SslKeyFile"
            }
            $sslCertPath = Join-Path $SecretsDir "backend_cert.pem"
            $sslKeyPath = Join-Path $SecretsDir "backend_key.pem"
            Copy-Item $SslCertFile $sslCertPath -Force
            Copy-Item $SslKeyFile $sslKeyPath -Force
            Write-Ok "Certificato fornito copiato in $SecretsDir"
        } else {
            Write-Step "Generazione certificato auto-firmato (per LAN - non per esposizione pubblica)"
            $sslCertPath = Join-Path $SecretsDir "backend_cert.pem"
            $sslKeyPath = Join-Path $SecretsDir "backend_key.pem"
            $ips = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" }).IPAddress
            & $pythonExe (Join-Path $ProjectRoot "backend\generate_cert.py") $sslCertPath $sslKeyPath $env:COMPUTERNAME @ips | Write-Host
            Assert-LastExitCode "generazione certificato"
        }
    }
}

if ($backendHost -eq "0.0.0.0") {
    Write-Step "Regola firewall (richiede sessione da amministratore)"
    try {
        $ruleName = "leank-spc backend ($backendPort)"
        if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
            New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -LocalPort $backendPort -Protocol TCP -Action Allow -ErrorAction Stop | Out-Null
        }
        Write-Ok "Regola firewall creata per la porta $backendPort"
    } catch {
        Write-WarnStep "Non sono riuscito a creare la regola firewall (serve una PowerShell da amministratore). Lanciare a mano, come amministratore:"
        Write-Host "   New-NetFirewallRule -DisplayName 'leank-spc backend' -Direction Inbound -LocalPort $backendPort -Protocol TCP -Action Allow" -ForegroundColor Yellow
    }
}

# -------------------------------------------------------------------------
# 4. Configurazione backend (.env) + migration
# -------------------------------------------------------------------------
Write-Step "Configurazione backend"
$jwtSecretFile = Join-Path $SecretsDir "jwt_secret.txt"
if (-not (Test-Path $jwtSecretFile)) {
    New-RandomSecret -Length 48 | Set-Content -NoNewline $jwtSecretFile
}
$jwtSecret = Get-Content $jwtSecretFile -Raw
$scheme = if ($sslCertPath) { "https" } else { "http" }
$sslLines = if ($sslCertPath) { "BACKEND_SSL_CERTFILE=$sslCertPath`nBACKEND_SSL_KEYFILE=$sslKeyPath" } else { "" }

@"
DATABASE_URL=postgresql+asyncpg://${PgUser}:${appPassword}@127.0.0.1:$PgPort/$PgDbName
BACKEND_HOST=$backendHost
BACKEND_PORT=$backendPort
$sslLines
JWT_SECRET=$jwtSecret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=14
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:$backendPort,https://127.0.0.1:$backendPort,null
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
Write-Host ""
if ($sslCertPath) {
    Write-Host "HTTPS attivo con certificato auto-firmato: il browser mostrera' un avviso 'connessione non sicura' - e' atteso, il traffico e' comunque cifrato. Procedere/accettare l'eccezione." -ForegroundColor Yellow
}
if ($backendHost -eq "0.0.0.0") {
    Write-Host "Backend raggiungibile da questo PC su:      $scheme`://127.0.0.1:$backendPort/docs"
    Write-Host "Backend raggiungibile da altre postazioni:  $scheme`://$env:COMPUTERNAME`:$backendPort/docs"
    $ips = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" }).IPAddress
    if ($ips) { Write-Host "                                    (oppure via IP: $($ips -join ', '))" }
    Write-Host "Usare uno di questi indirizzi (non 'localhost') nel config.yaml dell'Edge Agent su altre postazioni."
} else {
    Write-Host "Backend: $scheme`://127.0.0.1:$backendPort/docs (solo da questo PC)"
}
