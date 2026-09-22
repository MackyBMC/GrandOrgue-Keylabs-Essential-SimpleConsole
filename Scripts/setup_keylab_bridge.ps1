$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "KeyLab - GrandOrgue bridge setup"
Set-Location -LiteralPath $PSScriptRoot

function Find-Python {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) { return $launcher.Source }
    throw "Python was not found. Install Python and try again."
}

function Get-MidiPorts {
    param([string]$Python)

    $code = @'
import json
import mido
mido.set_backend("mido.backends.rtmidi")
print(json.dumps({"inputs": mido.get_input_names(), "outputs": mido.get_output_names()}))
'@
    $json = & $Python -c $code
    if ($LASTEXITCODE -ne 0) {
        throw "Could not query MIDI ports. Install requirements with install_requirements.bat."
    }
    return ($json -join "") | ConvertFrom-Json
}

function Select-Port {
    param(
        [string]$Title,
        [object[]]$Ports,
        [switch]$AllowBlank
    )

    Write-Host ""
    Write-Host $Title
    for ($i = 0; $i -lt $Ports.Count; $i++) {
        Write-Host ("  [{0}] {1}" -f ($i + 1), $Ports[$i])
    }
    if ($AllowBlank) { Write-Host "  [0] Leave unassigned / let GrandOrgue own it" }

    while ($true) {
        $choice = Read-Host "Select a port number"
        $number = 0
        if ([int]::TryParse($choice, [ref]$number)) {
            if ($AllowBlank -and $number -eq 0) { return "" }
            if ($number -ge 1 -and $number -le $Ports.Count) { return [string]$Ports[$number - 1] }
        }
        Write-Host "Enter one of the listed numbers."
    }
}

function Quote-Yaml {
    param([string]$Value)
    return '"' + $Value.Replace('"', '\"') + '"'
}

try {
    $python = Find-Python
    $ports = Get-MidiPorts -Python $python
    $inputs = @($ports.inputs)
    $outputs = @($ports.outputs)

    if ($inputs.Count -eq 0 -or $outputs.Count -eq 0) {
        throw "No MIDI input/output ports were found. Check the KeyLab and LoopBe installation."
    }

    Write-Host "Available MIDI ports" -ForegroundColor Cyan
    $go = Select-Port -Title "Select the virtual MIDI cable INPUT used by GrandOrgue (for example LoopBe Internal MIDI 0):" -Ports $inputs
    $goOut = Select-Port -Title "Select the virtual MIDI cable OUTPUT used by GrandOrgue (for example LoopBe Internal MIDI 1):" -Ports $outputs
    $keylabIn = Select-Port -Title "Select the KeyLab DAW INPUT used by the bridge:" -Ports $inputs
    $keylabOut = Select-Port -Title "Select the KeyLab OUTPUT used for LCD and LEDs:" -Ports $outputs
    $keylabMain = Select-Port -Title "Select the KeyLab MAIN INPUT for pad presses, or leave it with GrandOrgue:" -Ports $inputs -AllowBlank

    Write-Host ""
    Write-Host "Selected configuration:" -ForegroundColor Cyan
    Write-Host "  go:            $go"
    Write-Host "  go_out:        $goOut"
    Write-Host "  keylab_in:     $keylabIn"
    Write-Host "  keylab_out:    $keylabOut"
    Write-Host "  keylab_main_in:$keylabMain"
    $confirm = Read-Host "Write these values to config.yaml? (Y/N)"
    if ($confirm -notmatch '^(?i)y(es)?$') {
        Write-Host "Cancelled. No changes were made."
        exit 0
    }

    $configPath = Join-Path $PSScriptRoot "config.yaml"
    $content = Get-Content -LiteralPath $configPath -Raw
    $values = @{
        go = $go
        go_out = $goOut
        keylab_in = $keylabIn
        keylab_out = $keylabOut
        keylab_main_in = $keylabMain
    }
    foreach ($name in $values.Keys) {
        $replacement = "  {0}: {1}" -f $name, (Quote-Yaml $values[$name])
        $pattern = "(?m)^  " + [regex]::Escape($name) + ":.*$"
        $updated = [regex]::Replace($content, $pattern, $replacement, 1)
        if ($updated -eq $content) { throw "Could not find the '$name' entry in config.yaml." }
        $content = $updated
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($configPath, $content, $utf8NoBom)
    Write-Host ""
    Write-Host "config.yaml updated successfully." -ForegroundColor Green
    Write-Host "The bridge will use these settings on its next start."
}
catch {
    Write-Host "Setup failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}