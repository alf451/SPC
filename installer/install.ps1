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

.PARAMETER PostgresMode
  "Portable" (default): PostgreSQL portable in runtime\pgsql, nessun servizio
  Windows, nessun privilegio richiesto per questo passo - la modalita' pilota
  originale. "Full": usa un'installazione PostgreSQL vera con servizio Windows
  registrato - riusa un'installazione gia' presente sulla macchina se ce n'e'
  una (rilevata da sola), altrimenti scarica l'installer ufficiale EDB e lo
  esegue in modalita' silenziosa (richiede una sessione PowerShell da
  amministratore solo per questo passo).

.EXAMPLE
  .\install.ps1
  Interattivo: chiede porta, esposizione in rete, HTTPS e modalita' PostgreSQL
  con Enter per i default.

.EXAMPLE
  .\install.ps1 -Port 8080 -ExposeNetwork -Https
  Non interattivo, certificato auto-firmato generato in automatico, PostgreSQL portable.
#>
param(
    [int]$Port = 0,
    [switch]$ExposeNetwork,
    [switch]$Https,
    [string]$SslCertFile = "",
    [string]$SslKeyFile = "",
    [ValidateSet("", "Portable", "Full")]
    [string]$PostgresMode = ""
)

. "$PSScriptRoot\common.ps1"

Write-Host "=== leank-spc - installazione pilot mode ===" -ForegroundColor Magenta
Write-Host "Cartella progetto: $ProjectRoot"
Write-Host "Cartella runtime:  $RuntimeDir (tutto qui dentro, nulla fuori)"
Write-Host "ATTENZIONE: non premere Ctrl+C in questa finestra durante l'esecuzione, anche" -ForegroundColor Yellow
Write-Host "se sembra ferma per qualche minuto (es. durante il download o l'inizializzazione" -ForegroundColor Yellow
Write-Host "del database) - su Windows un Ctrl+C qui puo' arrestare in modo anomalo anche" -ForegroundColor Yellow
Write-Host "PostgreSQL, che condivide questa console (riscontrato dal vivo)." -ForegroundColor Yellow

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
# 2. PostgreSQL: portable (pilota) oppure installazione completa (servizio Windows)
# -------------------------------------------------------------------------
Write-Step "Modalita' PostgreSQL"
$postgresModeFile = Join-Path $RuntimeDir "postgres_mode.txt"
if ($PostgresMode -eq "" -and (Test-Path $postgresModeFile)) {
    $PostgresMode = (Get-Content $postgresModeFile -Raw).Trim()
    Write-Ok "Modalita' PostgreSQL gia' scelta in precedenza: $PostgresMode (invariata)"
} else {
    if ($PostgresMode -eq "") {
        if ([Environment]::UserInteractive) {
            $answer = Read-Host "PostgreSQL 'portable' (nessun servizio, tutto in runtime\pgsql, invio per questo default) o installazione 'completa' (servizio Windows vero, richiede amministratore)? [portable/completa]"
            $PostgresMode = if ($answer -match '^[cC]') { "Full" } else { "Portable" }
        } else {
            $PostgresMode = "Portable"
        }
    }
    Write-Ok "Modalita' PostgreSQL: $PostgresMode"
}
$PostgresMode | Set-FileContentNoNewline $postgresModeFile

if ($PostgresMode -eq "Full") {
    # ---------------------------------------------------------------------
    # 2a. PostgreSQL completo: riusa un'installazione esistente, o installane
    # una nuova con l'installer ufficiale EDB in modalita' silenziosa.
    #
    # NOTA IMPORTANTE: questo ramo non e' stato collaudato dal vivo (l'ambiente
    # di sviluppo non aveva una sessione con privilegi di amministratore
    # disponibile) - i parametri dell'installer silenzioso sono presi dalla
    # documentazione ufficiale EDB ma vanno verificati alla prima esecuzione
    # reale, idealmente su una macchina non critica prima di un cliente.
    # ---------------------------------------------------------------------
    $existingInstalls = Get-FullPostgresInstallations
    if ($existingInstalls.Count -gt 0) {
        $install = $existingInstalls[0]
        $baseDir = $install.'Base Directory'
        $dataDir = $install.'Data Directory'
        $psqlExe = Join-Path $baseDir "bin\psql.exe"
        $pgAppPort = Get-PostgresConfPort -DataDirectory $dataDir
        Write-Ok "Installazione PostgreSQL esistente trovata: $baseDir (porta $pgAppPort)"

        $pgSuperuserPasswordFile = Join-Path $SecretsDir "pg_superuser_password.txt"
        if (Test-Path $pgSuperuserPasswordFile) {
            $pgSuperuserPassword = Get-Content $pgSuperuserPasswordFile -Raw
        } else {
            Write-Host "   Serve la password dell'utente 'postgres' di questa installazione esistente (non generata da noi, non la conosciamo)." -ForegroundColor Yellow
            $secure = Read-Host "   Password superuser 'postgres'" -AsSecureString
            $pgSuperuserPassword = ConvertFrom-SecureStringToPlainText -SecureString $secure
            $pgSuperuserPassword | Set-FileContentNoNewline $pgSuperuserPasswordFile
        }

        $svc = Get-Service -Name (Split-Path $install.PSChildName -Leaf) -ErrorAction SilentlyContinue
        if ($svc -and $svc.Status -ne "Running") {
            Write-WarnStep "Il servizio PostgreSQL esistente non risulta 'Running' - avviarlo da Servizi.msc prima di continuare."
        }
    } else {
        if (-not (Test-IsAdministrator)) {
            throw "Installare PostgreSQL completo richiede una sessione PowerShell da amministratore (solo per questo passo - rilanciare install.ps1/install.cmd con 'Esegui come amministratore', oppure scegliere 'portable')."
        }

        $pgAppPort = $PgPortDefault
        if (Test-PortInUse -Port $pgAppPort) {
            Write-WarnStep "La porta $pgAppPort risulta gia' in uso da qualcosa che non e' un'installazione PostgreSQL registrata - verificare manualmente prima di continuare."
        }

        Write-Step "Download installer PostgreSQL completo (~350 MB)"
        $installerPath = Join-Path $downloadsDir "postgresql-installer.exe"
        Invoke-DownloadFile -Url $PgFullInstallerUrl -Destination $installerPath

        $pgSuperuserPasswordFile = Join-Path $SecretsDir "pg_superuser_password.txt"
        if (-not (Test-Path $pgSuperuserPasswordFile)) {
            New-RandomSecret | Set-FileContentNoNewline $pgSuperuserPasswordFile
        }
        $pgSuperuserPassword = Get-Content $pgSuperuserPasswordFile -Raw

        $servicePasswordFile = Join-Path $SecretsDir "pg_service_account_password.txt"
        if (-not (Test-Path $servicePasswordFile)) {
            New-RandomSecret | Set-FileContentNoNewline $servicePasswordFile
        }
        $servicePassword = Get-Content $servicePasswordFile -Raw

        Write-Step "Installazione PostgreSQL in corso (silenziosa, qualche minuto)"
        $installerArgs = @(
            "--mode", "unattended",
            "--unattendedmodeui", "minimal",
            "--superpassword", $pgSuperuserPassword,
            "--serviceaccount", "postgres",
            "--servicepassword", $servicePassword,
            "--servicename", "postgresql-leankspc",
            "--serverport", "$pgAppPort",
            "--disable-components", "stackbuilder",
            "--install_runtimes", "0"
        )
        $proc = Start-Process -FilePath $installerPath -ArgumentList $installerArgs -Wait -PassThru
        if ($proc.ExitCode -ne 0) {
            throw "Installer PostgreSQL terminato con codice $($proc.ExitCode) - vedi log installer in %TEMP% per i dettagli"
        }

        # L'installer di solito avvia gia' il servizio da solo: attendiamo comunque
        # fino a un minuto nel caso non fosse istantaneo.
        $svcReady = $false
        for ($i = 0; $i -lt 60; $i++) {
            $svc = Get-Service -Name "postgresql-leankspc" -ErrorAction SilentlyContinue
            if ($svc -and $svc.Status -eq "Running") { $svcReady = $true; break }
            Start-Sleep -Seconds 1
        }
        if (-not $svcReady) {
            Write-WarnStep "Il servizio 'postgresql-leankspc' non risulta 'Running' dopo l'installazione - controllare Servizi.msc"
        }

        $install = (Get-FullPostgresInstallations | Where-Object { $_.PSChildName -match "leankspc" } | Select-Object -First 1)
        if (-not $install) { $install = (Get-FullPostgresInstallations | Select-Object -First 1) }
        $psqlExe = Join-Path $install.'Base Directory' "bin\psql.exe"
        Write-Ok "PostgreSQL installato come servizio Windows 'postgresql-leankspc'"
    }

    $pgAppHostForPsql = "127.0.0.1"
} else {
    # ---------------------------------------------------------------------
    # 2b. PostgreSQL portable (zip binari, nessun MSI/servizio) - modalita' originale
    # ---------------------------------------------------------------------
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
        New-RandomSecret | Set-FileContentNoNewline $pgSuperuserPasswordFile
    }
    $pgSuperuserPassword = Get-Content $pgSuperuserPasswordFile -Raw

    if (-not (Test-Path (Join-Path $PgDataDir "PG_VERSION"))) {
        Write-Step "Inizializzazione data directory PostgreSQL"
        $initdb = Join-Path $PgDir "pgsql\bin\initdb.exe"
        $pwFile = Join-Path $downloadsDir "pg_superuser_pwfile.tmp"
        Set-FileContentNoNewline -Path $pwFile -Value $pgSuperuserPassword
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
        # "pg_ctl start" puo' fallire/andare in timeout senza che $LASTEXITCODE lo
        # rifletta in modo affidabile qui (dipende da come pg_ctl -w restituisce il
        # controllo) - senza questo controllo esplicito lo script proseguiva comunque
        # fino alla migration, dove l'errore compariva mascherato e fuorviante
        # ("ConnectionRefusedError" su alembic invece del vero problema). Riscontrato
        # dal vivo spostando runtime\pgdata da un'altra cartella progetto: se il
        # vecchio processo non era stato fermato prima, restava un postmaster.pid
        # non valido che impediva il riavvio pulito nella nuova posizione.
        if (-not (Test-PostgresRunning)) {
            throw "PostgreSQL non risulta avviato dopo 'pg_ctl start' - controllare $logFile per l'errore esatto. Causa comune: la cartella runtime\ e' stata spostata/copiata da un'altra cartella progetto senza prima fermare PostgreSQL li' (installer\stop.ps1) - in quel caso cancellare runtime\pgdata\postmaster.pid (se presente) e rilanciare."
        }
    } else {
        Write-Ok "PostgreSQL gia' in esecuzione"
    }

    $psqlExe = Get-PsqlExe
    $pgAppPort = $PgPort
    $pgAppHostForPsql = "127.0.0.1"
}

Write-Step "Creazione database applicativo"
$env:PGPASSWORD = $pgSuperuserPassword
$appPasswordFile = Join-Path $SecretsDir "pg_app_password.txt"
if (-not (Test-Path $appPasswordFile)) {
    New-RandomSecret | Set-FileContentNoNewline $appPasswordFile
}
$appPassword = Get-Content $appPasswordFile -Raw

$roleExists = & $psqlExe -h $pgAppHostForPsql -p $pgAppPort -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$PgUser'" postgres
if (-not $roleExists -or $roleExists.Trim() -ne "1") {
    & $psqlExe -h $pgAppHostForPsql -p $pgAppPort -U postgres -c "CREATE ROLE $PgUser LOGIN PASSWORD '$appPassword';" postgres | Write-Host
}
$dbExists = & $psqlExe -h $pgAppHostForPsql -p $pgAppPort -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$PgDbName'" postgres
if (-not $dbExists -or $dbExists.Trim() -ne "1") {
    & $psqlExe -h $pgAppHostForPsql -p $pgAppPort -U postgres -c "CREATE DATABASE $PgDbName OWNER $PgUser;" postgres | Write-Host
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
        # Un input non numerico (es. risposto per sbaglio al prompt sbagliato,
        # come una password) non deve far crashare l'intero installer con un
        # errore .NET criptico - si ri-chiede finche' non arriva o un numero
        # valido o l'invio a vuoto (default). Riscontrato dal vivo.
        $backendPort = $BackendPortDefault
        while ($true) {
            $answer = Read-Host "Porta del backend [invio per $BackendPortDefault]"
            if (-not $answer) { break }
            $parsedPort = 0
            if ([int]::TryParse($answer, [ref]$parsedPort) -and $parsedPort -gt 0 -and $parsedPort -le 65535) {
                $backendPort = $parsedPort
                break
            }
            Write-Host "   '$answer' non e' un numero di porta valido (1-65535) - riprova, oppure premi invio per usare $BackendPortDefault." -ForegroundColor Yellow
        }
    } else {
        $backendPort = if ($Port -ne 0) { $Port } else { $BackendPortDefault }
    }
    if (Test-PortInUse -Port $backendPort) {
        Write-WarnStep "La porta $backendPort risulta gia' in uso da un altro programma (es. IIS) - scegline un'altra."
    }

    # Rilevata qui (non solo nel riepilogo finale) per poterla proporre come
    # default nella domanda sulla raggiungibilita' in rete: piu' concreto di un
    # generico "si/no", e l'utente vede subito l'indirizzo che verra' usato.
    $detectedIp = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | Select-Object -First 1).IPAddress

    if ($interactive) {
        if ($detectedIp) {
            $answer = Read-Host "Indirizzo su cui rendere raggiungibile il backend [invio per $detectedIp - raggiungibile anche dalla rete; scrivere '127.0.0.1' o 'localhost' per limitarlo a questo PC]"
            $ExposeNetwork = -not ($answer.Trim() -match '^(127\.0\.0\.1|localhost)$')
        } else {
            $answer = Read-Host "Raggiungibile anche da altre macchine della rete, non solo da questo PC? [s/N]"
            $ExposeNetwork = $answer -match '^[sS]'
        }
    }
    $backendHost = if ($ExposeNetwork) { "0.0.0.0" } else { "127.0.0.1" }
    if ($ExposeNetwork -and $detectedIp) {
        Write-Ok "Backend su 0.0.0.0:$backendPort (raggiungibile anche su $detectedIp`:$backendPort)"
    } else {
        Write-Ok "Backend su $backendHost`:$backendPort"
    }

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
    New-RandomSecret -Length 48 | Set-FileContentNoNewline $jwtSecretFile
}
$jwtSecret = Get-Content $jwtSecretFile -Raw
$scheme = if ($sslCertPath) { "https" } else { "http" }
$sslLines = if ($sslCertPath) { "BACKEND_SSL_CERTFILE=$sslCertPath`nBACKEND_SSL_KEYFILE=$sslKeyPath" } else { "" }

@"
DATABASE_URL=postgresql+asyncpg://${PgUser}:${appPassword}@127.0.0.1:$pgAppPort/$PgDbName
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
    New-RandomSecret -Length 16 | Set-FileContentNoNewline $adminPasswordFile
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
