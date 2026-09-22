$Host.UI.RawUI.WindowTitle = "KeyLab - GrandOrgue bridge"
Set-Location -LiteralPath $PSScriptRoot

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    $python = Get-Command py -ErrorAction SilentlyContinue
}

if (-not $python) {
    Write-Host "Python was not found. Install Python and try again."
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host "Starting the KeyLab - GrandOrgue bridge. Close this window or press Ctrl+C to stop."
Write-Host ""

& $python.Source (Join-Path $PSScriptRoot "keylab_go_bridge.py") @args
$exitCode = $LASTEXITCODE

if ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "The bridge stopped with an error - see the message above."
    Write-Host "If it says 'No module named', run install_requirements.bat once."
    Read-Host "Press Enter to close"
}

exit $exitCode