<#
.SYNOPSIS
  Strumento diagnostico: scopre i PC raggiungibili in una sottorete e ne
  elenca le porte COM / dispositivi USB collegati, interrogandoli via WMI da
  QUESTA macchina - senza dover accedere fisicamente o via RDP a ciascuna
  postazione. Non fa parte dell'app in produzione.

.DESCRIPTION
  Non e' una pagina web: un browser non ha modo di scansionare una rete o
  interrogare WMI su un'altra macchina, quindi questo e' uno script
  PowerShell con una piccola interfaccia grafica nativa (Windows Forms).

  Interroga i PC remoti con Get-CimInstance -ComputerName (WMI/DCOM), NON
  richiede PowerShell Remoting/WinRM abilitato - piu' probabile che funzioni
  "di serie" su una LAN aziendale tipica. Serve pero' che il firewall del PC
  remoto permetta "Windows Management Instrumentation (WMI)" in ingresso, e
  credenziali con diritti sufficienti su quella macchina (per default usa
  l'utente della sessione corrente; c'e' un'opzione per specificarne altre).

.NOTES
  Eseguire con: powershell -ExecutionPolicy Bypass -File network-device-scanner.ps1
  (o doppio click se l'associazione file .ps1 lo permette)
#>

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# -------------------------------------------------------------------------
# Finestra principale
# -------------------------------------------------------------------------
$form = New-Object System.Windows.Forms.Form
$form.Text = "leank-spc - Scansione rete e dispositivi COM/USB"
$form.Size = New-Object System.Drawing.Size(900, 660)
$form.MinimumSize = $form.Size
$form.StartPosition = "CenterScreen"

$lblSubnet = New-Object System.Windows.Forms.Label
$lblSubnet.Text = "Sottorete (es. 192.168.1):"
$lblSubnet.Location = New-Object System.Drawing.Point(10, 15)
$lblSubnet.AutoSize = $true
$form.Controls.Add($lblSubnet)

$txtSubnet = New-Object System.Windows.Forms.TextBox
$txtSubnet.Location = New-Object System.Drawing.Point(180, 12)
$txtSubnet.Width = 140
# precompilata con la sottorete di questo PC, se rilevabile
try {
    $localIp = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
        Select-Object -First 1).IPAddress
    if ($localIp) {
        $parts = $localIp -split '\.'
        $txtSubnet.Text = "$($parts[0]).$($parts[1]).$($parts[2])"
    }
} catch {}
$form.Controls.Add($txtSubnet)

$btnScan = New-Object System.Windows.Forms.Button
$btnScan.Text = "Scansiona rete (.1 - .254)"
$btnScan.Location = New-Object System.Drawing.Point(330, 10)
$btnScan.Width = 170
$form.Controls.Add($btnScan)

$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = ""
$lblStatus.Location = New-Object System.Drawing.Point(510, 15)
$lblStatus.AutoSize = $true
$form.Controls.Add($lblStatus)

$lblPcs = New-Object System.Windows.Forms.Label
$lblPcs.Text = "PC raggiungibili (doppio click per interrogare):"
$lblPcs.Location = New-Object System.Drawing.Point(10, 45)
$lblPcs.AutoSize = $true
$form.Controls.Add($lblPcs)

$listPcs = New-Object System.Windows.Forms.ListView
$listPcs.View = "Details"
$listPcs.FullRowSelect = $true
$listPcs.GridLines = $true
$listPcs.Location = New-Object System.Drawing.Point(10, 65)
$listPcs.Size = New-Object System.Drawing.Size(400, 260)
$listPcs.Anchor = "Top, Bottom, Left"
[void]$listPcs.Columns.Add("IP", 130)
[void]$listPcs.Columns.Add("Nome host", 230)
$form.Controls.Add($listPcs)

$chkCred = New-Object System.Windows.Forms.CheckBox
$chkCred.Text = "Usa credenziali diverse da quelle di questa sessione"
$chkCred.Location = New-Object System.Drawing.Point(10, 330)
$chkCred.AutoSize = $true
$chkCred.Anchor = "Bottom, Left"
$form.Controls.Add($chkCred)

$btnListDevices = New-Object System.Windows.Forms.Button
$btnListDevices.Text = "Elenca dispositivi COM/USB sul PC selezionato ->"
$btnListDevices.Location = New-Object System.Drawing.Point(10, 355)
$btnListDevices.Width = 400
$btnListDevices.Anchor = "Bottom, Left"
$form.Controls.Add($btnListDevices)

$txtLog = New-Object System.Windows.Forms.TextBox
$txtLog.Multiline = $true
$txtLog.ScrollBars = "Vertical"
$txtLog.ReadOnly = $true
$txtLog.Font = New-Object System.Drawing.Font("Consolas", 8.5)
$txtLog.Location = New-Object System.Drawing.Point(10, 390)
$txtLog.Size = New-Object System.Drawing.Size(400, 220)
$txtLog.Anchor = "Top, Bottom, Left"
$form.Controls.Add($txtLog)

$lblDevices = New-Object System.Windows.Forms.Label
$lblDevices.Text = "Dispositivi COM/USB sul PC selezionato:"
$lblDevices.Location = New-Object System.Drawing.Point(430, 45)
$lblDevices.AutoSize = $true
$form.Controls.Add($lblDevices)

$listDevices = New-Object System.Windows.Forms.ListView
$listDevices.View = "Details"
$listDevices.FullRowSelect = $true
$listDevices.GridLines = $true
$listDevices.Location = New-Object System.Drawing.Point(430, 65)
$listDevices.Size = New-Object System.Drawing.Size(440, 545)
$listDevices.Anchor = "Top, Bottom, Left, Right"
[void]$listDevices.Columns.Add("Nome dispositivo", 280)
[void]$listDevices.Columns.Add("Classe PnP", 140)
$form.Controls.Add($listDevices)

function Write-Log {
    param([string]$Message)
    $ts = Get-Date -Format "HH:mm:ss"
    $txtLog.AppendText("[$ts] $Message`r`n")
}

# -------------------------------------------------------------------------
# Scansione rete: ping asincrono su tutto l'intervallo .1-.254, in parallelo
# -------------------------------------------------------------------------
$btnScan.Add_Click({
    $listPcs.Items.Clear()
    $subnet = $txtSubnet.Text.Trim().TrimEnd('.')
    if (-not $subnet) {
        Write-Log "Inserire una sottorete, es. 192.168.1"
        return
    }

    $btnScan.Enabled = $false
    $lblStatus.Text = "Scansione in corso..."
    $form.Refresh()
    Write-Log "Scansione di $subnet.1-254 (ping, timeout 300ms)..."

    $pingers = @()
    for ($i = 1; $i -le 254; $i++) {
        $ip = "$subnet.$i"
        $ping = New-Object System.Net.NetworkInformation.Ping
        $task = $ping.SendPingAsync($ip, 300)
        $pingers += [PSCustomObject]@{ IP = $ip; Ping = $ping; Task = $task }
    }

    [System.Threading.Tasks.Task]::WaitAll($pingers.Task) | Out-Null

    $found = 0
    foreach ($p in $pingers) {
        try {
            $reply = $p.Task.Result
            if ($reply.Status -eq [System.Net.NetworkInformation.IPStatus]::Success) {
                $hostname = ""
                try { $hostname = [System.Net.Dns]::GetHostEntry($p.IP).HostName } catch {}
                $item = New-Object System.Windows.Forms.ListViewItem($p.IP)
                [void]$item.SubItems.Add($hostname)
                [void]$listPcs.Items.Add($item)
                $found++
            }
        } catch {
        } finally {
            $p.Ping.Dispose()
        }
    }

    $lblStatus.Text = "Trovati $found PC raggiungibili."
    Write-Log "Scansione completata: $found PC rispondono al ping su $subnet.0/24."
    Write-Log "Nota: un PC puo' non rispondere al ping ma essere comunque raggiungibile via WMI (ICMP a volte bloccato dal firewall separatamente da WMI) - se sai gia' il nome/IP puoi comunque provare 'Elenca dispositivi' scrivendolo direttamente in un elemento selezionato, oppure aggiungerlo qui sotto."
    $btnScan.Enabled = $true
})

# -------------------------------------------------------------------------
# Interrogazione WMI del PC selezionato
# -------------------------------------------------------------------------
function Get-RemoteComUsbDevices {
    param([string]$ComputerName, [System.Management.Automation.PSCredential]$Credential)

    $params = @{ ComputerName = $ComputerName; ClassName = "Win32_PnPEntity"; ErrorAction = "Stop" }
    if ($Credential) { $params.Credential = $Credential }

    $all = Get-CimInstance @params
    return $all | Where-Object {
        $_.Name -match 'COM\d+' -or
        $_.PNPClass -eq 'Ports' -or
        $_.PNPClass -eq 'USB' -or
        ($_.Name -and $_.Name -match 'USB')
    } | Sort-Object Name
}

function Invoke-DeviceScan {
    param([string]$Target)

    $listDevices.Items.Clear()
    if (-not $Target) {
        Write-Log "Nessun PC selezionato."
        return
    }

    Write-Log "Interrogo $Target via WMI (Win32_PnPEntity)..."
    $form.Cursor = [System.Windows.Forms.Cursors]::WaitCursor

    $cred = $null
    if ($chkCred.Checked) {
        $cred = Get-Credential -Message "Credenziali per $Target"
        if (-not $cred) {
            Write-Log "Annullato dall'utente."
            $form.Cursor = [System.Windows.Forms.Cursors]::Default
            return
        }
    }

    try {
        $devices = Get-RemoteComUsbDevices -ComputerName $Target -Credential $cred
        if (-not $devices) {
            Write-Log "Nessun dispositivo COM/USB trovato su $Target (o WMI non ha restituito nulla)."
        } else {
            foreach ($d in $devices) {
                $item = New-Object System.Windows.Forms.ListViewItem($d.Name)
                [void]$item.SubItems.Add($d.PNPClass)
                [void]$listDevices.Items.Add($item)
            }
            Write-Log "Trovati $($devices.Count) dispositivi COM/USB su $Target."
        }
    } catch {
        Write-Log "ERRORE interrogando ${Target}: $($_.Exception.Message)"
        Write-Log "Cause piu' probabili: firewall del PC remoto blocca WMI in ingresso (serve l'eccezione 'Windows Management Instrumentation (WMI)' nel Windows Firewall di quel PC), credenziali senza diritti sufficienti (prova la casella 'Usa credenziali diverse'), oppure il PC non e' raggiungibile in rete/dominio compatibile con DCOM."
    } finally {
        $form.Cursor = [System.Windows.Forms.Cursors]::Default
    }
}

$btnListDevices.Add_Click({
    if ($listPcs.SelectedItems.Count -eq 0) {
        Write-Log "Seleziona un PC dall'elenco a sinistra (o fai doppio click su una riga)."
        return
    }
    Invoke-DeviceScan -Target $listPcs.SelectedItems[0].Text
})

$listPcs.Add_DoubleClick({
    if ($listPcs.SelectedItems.Count -gt 0) {
        Invoke-DeviceScan -Target $listPcs.SelectedItems[0].Text
    }
})

Write-Log "Pronto. Inserisci una sottorete e premi 'Scansiona rete', oppure seleziona/aggiungi direttamente un PC se lo conosci gia'."

[void]$form.ShowDialog()
