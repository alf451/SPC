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
$script:BackendPort = 8000
$script:PgDbName = "leank_spc"
$script:PgUser = "leank_spc"

$script:PythonEmbedUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
$script:PgBinariesUrl = "https://get.enterprisedb.com/postgresql/postgresql-17.10-2-windows-x64-binaries.zip"
# Se questi URL smettono di funzionare (EDB/python.org possono spostare i file),
# aggiornarli da https://www.enterprisedb.com/download-postgresql-binaries e
# https://www.python.org/downloads/windows/ (cercare "embeddable package").

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

function Test-PostgresRunning {
    $pgCtl = Get-PgCtlExe
    if (-not (Test-Path $pgCtl)) { return $false }
    $result = & $pgCtl status -D $PgDataDir 2>&1
    return $LASTEXITCODE -eq 0
}

function Test-BackendRunning {
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/health" -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
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
