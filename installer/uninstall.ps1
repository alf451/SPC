<#
.SYNOPSIS
  Rimuove completamente l'installazione pilot mode: ferma i processi ed
  elimina la cartella runtime\. Il codice sorgente del progetto (backend/,
  edge-agent/, docs/) NON viene toccato. Nessuna traccia lasciata sul PC
  (nessun servizio, nessuna chiave di registro, nessun file fuori dal progetto).
#>

. "$PSScriptRoot\common.ps1"

$postgresMode = Get-PostgresMode
if ($postgresMode -eq "Full") {
    Write-Host "Questo rimuove i pacchetti Python e i dati in $RuntimeDir. NON tocca l'installazione PostgreSQL completa (fuori da questa cartella) ne' il servizio Windows." -ForegroundColor Yellow
} else {
    Write-Host "Questo rimuove PostgreSQL portable, i pacchetti Python e TUTTI I DATI in $RuntimeDir." -ForegroundColor Yellow
}
$confirm = Read-Host "Confermi? (scrivi 'si' per procedere)"
if ($confirm -ne "si") {
    Write-Host "Annullato."
    exit 0
}

& "$PSScriptRoot\stop.ps1"

Write-Step "Rimozione runtime"
if (Test-Path $RuntimeDir) {
    Remove-Item -Recurse -Force $RuntimeDir
    Write-Ok "Cartella $RuntimeDir eliminata"
} else {
    Write-Ok "Nulla da rimuovere"
}

$envFile = Join-Path $ProjectRoot "backend\.env"
if (Test-Path $envFile) {
    Remove-Item $envFile
    Write-Ok "Rimosso backend\.env"
}

Write-Host ""
Write-Host "Disinstallazione completata." -ForegroundColor Green
if ($postgresMode -eq "Full") {
    Write-Host ""
    Write-Host "PostgreSQL completo NON e' stato rimosso (potrebbe contenere dati importanti, o essere usato da altro)." -ForegroundColor Yellow
    Write-Host "Per rimuoverlo: Pannello di controllo > Programmi e funzionalita' > PostgreSQL, oppure:"
    Write-Host "  Stop-Service postgresql-leankspc; sc.exe delete postgresql-leankspc"
} else {
    Write-Host "Il sistema e' come prima dell'installazione."
}
