<#
.SYNOPSIS
  Ferma il backend leank-spc e PostgreSQL, in modo pulito.
#>

. "$PSScriptRoot\common.ps1"

Write-Step "Backend FastAPI"
$pidFile = Join-Path $RuntimeDir "backend.pid"
if (Test-Path $pidFile) {
    $processId = Get-Content $pidFile
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $processId -Force
        Write-Ok "Fermato (PID $processId)"
    } else {
        Write-Ok "Non risultava attivo"
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
} else {
    Write-Ok "Nessun processo da fermare"
}

Write-Step "PostgreSQL"
if ((Get-PostgresMode) -eq "Full") {
    Write-Ok "Installazione completa: resta attivo, gestito da Windows come servizio ('Stop-Service postgresql-leankspc' se davvero serve fermarlo)"
} elseif (Test-Path (Get-PgCtlExe)) {
    if (Test-PostgresRunning) {
        & (Get-PgCtlExe) stop -D $PgDataDir -m fast | Write-Host
        Write-Ok "Fermato"
    } else {
        Write-Ok "Non era in esecuzione"
    }
} else {
    Write-Ok "Non installato"
}
