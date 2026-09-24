$Host.UI.RawUI.WindowTitle = "KeyLab - GrandOrgue"
Set-Location -LiteralPath $PSScriptRoot

$grandOrgue = if ($env:GRANDORGUE_EXE) {
    $env:GRANDORGUE_EXE
} else {
    @(
        (Join-Path ${env:ProgramFiles} "GrandOrgue\GrandOrgue.exe"),
        (Join-Path ${env:ProgramFiles} "GrandOrgue\bin\GrandOrgue.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "GrandOrgue\GrandOrgue.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "GrandOrgue\bin\GrandOrgue.exe"),
        "GrandOrgue.exe"
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
}
$configPath = Join-Path $PSScriptRoot "config.yaml"
$configuredOrgan = $null
if (Test-Path -LiteralPath $configPath) {
    $configText = Get-Content -LiteralPath $configPath -Raw
    if ($configText -match '(?m)^\s*organ_path:\s*([''\"])(.*?)\1\s*(?:#.*)?$') {
        $configuredOrgan = $Matches[2]
    }
}

$organ = if ($env:GRANDORGUE_ORGUE) {
    $env:GRANDORGUE_ORGUE
} elseif ($configuredOrgan) {
    $configuredOrgan
} else {
    Join-Path (Split-Path -Parent $PSScriptRoot) "Organs\PiteaMHS20250727.orgue"
}

if (-not $grandOrgue -and -not (Get-Command "GrandOrgue.exe" -ErrorAction SilentlyContinue)) {
    Write-Host "GrandOrgue.exe was not found. Set GRANDORGUE_EXE to its full path and try again."
    Read-Host "Press Enter to close"
    exit 1
}

$bridge = Join-Path $PSScriptRoot "start_keylab_bridge.ps1"
Write-Host "Starting the KeyLab bridge..."
Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $bridge
) -WorkingDirectory $PSScriptRoot

Start-Sleep -Seconds 2

$arguments = @()
if (Test-Path -LiteralPath $organ) {
    $arguments += '"' + $organ + '"'
    Write-Host "Loading organ: $organ"
} else {
    Write-Host "Organ package not found; starting GrandOrgue without one: $organ"
}

Write-Host "Starting GrandOrgue..."
$grandOrgueCommand = if ($grandOrgue) { $grandOrgue } else { "GrandOrgue.exe" }
$grandOrgueDirectory = Split-Path -Parent $grandOrgueCommand
if (-not $grandOrgueDirectory) { $grandOrgueDirectory = (Get-Location).Path }
if (Get-Process -Name "GrandOrgue" -ErrorAction SilentlyContinue) {
    Write-Host "GrandOrgue is already running; leaving the existing instance open."
} elseif ($arguments.Count -gt 0) {
    Start-Process -FilePath $grandOrgueCommand -ArgumentList $arguments -WorkingDirectory $grandOrgueDirectory
} else {
    Start-Process -FilePath $grandOrgueCommand -WorkingDirectory $grandOrgueDirectory
}
Write-Host "The bridge remains running in its own window. Close it when finished."