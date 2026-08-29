# Funzioni condivise dagli script installer/*.ps1.
# Nessuna di queste richiede privilegi di amministratore: tutto vive dentro
# $RuntimeDir (di default <progetto>\runtime), cancellabile senza lasciare
# traccia nel sistema (nessun servizio Windows, nessuna chiave di registro).

$ErrorActionPreference = "Stop"

# Windows Server datati (2012/2012 R2) spesso hanno .NET Framework configurato
# a non negoziare TLS 1.2 di default: i download da python.org/enterprisedb.com
# falliscono in modo silenzioso/criptico senza questa riga. Innocuo su Windows
# recenti (dove TLS 1.2 e' gia' il default).
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch {
    Write-Host "ATTENZIONE: impossibile forzare TLS 1.2 esplicitamente ($($_.Exception.Message)) - se i download falliscono, e' probabilmente questo." -ForegroundColor Yellow
}

$script:ProjectRoot = Split-Path -Parent $PSScriptRoot
$script:RuntimeDir = Join-Path $ProjectRoot "runtime"
$script:PythonDir = Join-Path $RuntimeDir "python"
$script:PgDir = Join-Path $RuntimeDir "pgsql"
$script:PgDataDir = Join-Path $RuntimeDir "pgdata"
$script:LogsDir = Join-Path $RuntimeDir "logs"
$script:SecretsDir = Join-Path $RuntimeDir "secrets"
$script:PgPort = 5433
$script:BackendPortDefault = 8000
$script:PgDbName = "leank_spc"
$script:PgUser = "leank_spc"
$script:EnvFile = Join-Path $ProjectRoot "backend\.env"

$script:PythonEmbedUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
$script:PgBinariesUrl = "https://get.enterprisedb.com/postgresql/postgresql-17.10-2-windows-x64-binaries.zip"
$script:PgFullInstallerUrl = "https://get.enterprisedb.com/postgresql/postgresql-17.11-1-windows-x64.exe"
$script:PgPortDefault = 5432
# Se questi URL smettono di funzionare (EDB/python.org possono spostare i file),
# aggiornarli da https://www.enterprisedb.com/download-postgresql-binaries
# (per PgBinariesUrl), https://www.enterprisedb.com/downloads/postgres-postgresql-downloads
# (per PgFullInstallerUrl, il vero installer grafico - non il file "binaries")
# e https://www.python.org/downloads/windows/ (cercare "embeddable package").

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host ">> $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "   OK: $Message" -ForegroundColor Green
}

function Write-WarnStep {
    param([string]$Message)
    Write-Host "   ATTENZIONE: $Message" -ForegroundColor Yellow
}

function Assert-Dir {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Invoke-DownloadFile {
    param(
        [string]$Url,
        [string]$Destination,
        [int]$MaxRetries = 3
    )
    if (Test-Path $Destination) {
        Write-Ok "Gia' presente: $(Split-Path -Leaf $Destination)"
        return
    }
    Assert-Dir (Split-Path -Parent $Destination)
    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        try {
            Write-Host "   Download ($attempt/$MaxRetries): $Url"
            Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
            Write-Ok "Scaricato in $Destination"
            return
        } catch {
            Write-WarnStep "Tentativo $attempt fallito: $($_.Exception.Message)"
            if ($attempt -eq $MaxRetries) { throw }
            Start-Sleep -Seconds (3 * $attempt)
        }
    }
}

function Get-PythonExe {
    Join-Path $PythonDir "python.exe"
}

function Get-PgCtlExe {
    Join-Path $PgDir "pgsql\bin\pg_ctl.exe"
}

function Get-PsqlExe {
    Join-Path $PgDir "pgsql\bin\psql.exe"
}

function Get-PostgresMode {
    # "Portable" (default) o "Full" - scelto durante install.ps1, persistito
    # qui perche' start.ps1/stop.ps1 sappiano se devono occuparsi loro di
    # avviare/fermare Postgres (portable) o lasciarlo al servizio Windows (full).
    $modeFile = Join-Path $RuntimeDir "postgres_mode.txt"
    if (Test-Path $modeFile) { return (Get-Content $modeFile -Raw).Trim() }
    return "Portable"
}

function Test-PostgresRunning {
    $pgCtl = Get-PgCtlExe
    if (-not (Test-Path $pgCtl)) { return $false }
    $result = & $pgCtl status -D $PgDataDir 2>&1
    return $LASTEXITCODE -eq 0
}

function Get-EnvValue {
    # Legge KEY=valore da backend/.env. Ritorna $Default se il file o la
    # chiave non esistono (es. primo avvio di install.ps1, prima che scriva .env).
    param([string]$Key, [string]$Default)
    if (-not (Test-Path $EnvFile)) { return $Default }
    $line = Get-Content $EnvFile | Where-Object { $_ -match "^$Key=" } | Select-Object -First 1
    if (-not $line) { return $Default }
    return ($line -split '=', 2)[1].Trim()
}

function Get-BackendPort {
    Get-EnvValue -Key "BACKEND_PORT" -Default $BackendPortDefault
}

function Get-BackendHost {
    Get-EnvValue -Key "BACKEND_HOST" -Default "127.0.0.1"
}

function Get-BackendScheme {
    if (Get-EnvValue -Key "BACKEND_SSL_CERTFILE" -Default "") { "https" } else { "http" }
}

function Test-PortInUse {
    param([int]$Port)
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $Port)
        $listener.Start()
        $listener.Stop()
        return $false
    } catch {
        return $true
    }
}

function Test-BackendRunning {
    # Controlla sempre via 127.0.0.1: funziona sia che il backend ascolti solo
    # in locale sia che ascolti anche in rete (0.0.0.0 accetta comunque
    # connessioni dallo stesso PC su 127.0.0.1).
    $port = Get-BackendPort
    $scheme = Get-BackendScheme

    if ($scheme -eq "https") {
        Enable-TrustAllCertificates
    }
    try {
        $response = Invoke-WebRequest -Uri "$scheme`://127.0.0.1:$port/health" -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Enable-TrustAllCertificates {
    # Windows PowerShell 5.1 non ha "-SkipCertificateCheck" (solo PS7+): per
    # verificare un backend HTTPS con certificato auto-firmato serve disattivare
    # la validazione, altrimenti Invoke-WebRequest la rifiuta sempre (anche
    # verso 127.0.0.1). Assegnare uno scriptblock a
    # ServerCertificateValidationCallback NON funziona in modo affidabile su
    # PS 5.1 ("Spazio di esecuzione non disponibile": il .NET Framework invoca
    # il callback su un thread senza runspace PowerShell) - la via collaudata e'
    # la vecchia interfaccia ICertificatePolicy (deprecata ma funzionante),
    # assegnando un'istanza di una classe vera invece di un delegate.
    # Impostazione valida per l'intero processo: adatto per uno script
    # installer/start "usa e getta", non da fare in un'app di lunga durata.
    if (-not ("LeankSpcTrustAllCertsPolicy" -as [type])) {
        Add-Type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
public class LeankSpcTrustAllCertsPolicy : ICertificatePolicy {
    public bool CheckValidationResult(ServicePoint srvPoint, X509Certificate certificate, WebRequest request, int certificateProblem) {
        return true;
    }
}
"@
    }
    [System.Net.ServicePointManager]::CertificatePolicy = New-Object LeankSpcTrustAllCertsPolicy
}

function Assert-LastExitCode {
    param([string]$Context)
    if ($LASTEXITCODE -ne 0) {
        throw "Comando fallito ($Context), exit code $LASTEXITCODE - vedi output sopra"
    }
}

function Expand-ZipFile {
    param([string]$ZipPath, [string]$Destination)
    # Expand-Archive esiste solo da PowerShell 5.0 in poi: su Server 2012/2012 R2
    # (PowerShell 3.0/4.0 di serie) non c'e'. .NET Framework's ZipFile funziona
    # gia' da .NET 4.5 (presente di serie anche su Server 2012), quindi e' la
    # via compatibile con qualunque versione di PowerShell.
    Assert-Dir $Destination
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($ZipPath, $Destination)
}

function Test-IsAdministrator {
    ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function ConvertFrom-SecureStringToPlainText {
    # PS 5.1 non ha "ConvertFrom-SecureString -AsPlainText" (solo PS7+).
    param([Security.SecureString]$SecureString)
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($SecureString)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringUni($ptr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeGlobalAllocUnicode($ptr)
    }
}

function Get-FullPostgresInstallations {
    # Ogni installazione "completa" (installer ufficiale EDB, non la nostra
    # portable) si registra sotto questa chiave, una sottochiave per versione/
    # istanza installata. Ritorna array vuoto (non $null) se non ce n'e' nessuna,
    # cosi' il chiamante puo' sempre fare .Count senza controlli aggiuntivi.
    $installs = Get-ItemProperty "HKLM:\SOFTWARE\PostgreSQL\Installations\*" -ErrorAction SilentlyContinue
    if ($null -eq $installs) { return @() }
    return @($installs)
}

function Get-PostgresConfPort {
    # Il registro non riporta sempre la porta configurata: va letta da
    # postgresql.conf nella Data Directory. Se la riga "port" e' commentata
    # (default di fabbrica), PostgreSQL usa 5432.
    param([string]$DataDirectory)
    $confPath = Join-Path $DataDirectory "postgresql.conf"
    if (-not (Test-Path $confPath)) { return $PgPortDefault }
    $line = Get-Content $confPath | Where-Object { $_ -match '^\s*port\s*=\s*(\d+)' } | Select-Object -First 1
    if ($line -and ($line -match '(\d+)')) { return [int]$Matches[1] }
    return $PgPortDefault
}

function New-RandomSecret {
    param([int]$Length = 32)
    # RandomNumberGenerator::Fill (statico) esiste solo in .NET moderno: su Windows
    # PowerShell 5.1 (.NET Framework, quello che gira di default sui PC client) non
    # e' disponibile - si usa quindi l'API basata su istanza, compatibile con entrambi.
    $bytes = New-Object byte[] $Length
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($bytes) -replace '[^a-zA-Z0-9]', ''
}
