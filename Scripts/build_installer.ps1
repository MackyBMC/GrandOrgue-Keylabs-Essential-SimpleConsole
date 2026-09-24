$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$iss = Join-Path $root "Installer\KeyLabGrandOrgue.iss"
$exe = Join-Path $PSScriptRoot "build\keylab_go_bridge.exe"

if (-not (Test-Path -LiteralPath $exe)) {
    throw "Compiled bridge not found: $exe. Run compile_bridge.bat first."
}

$candidates = @(
    (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source,
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1

if (-not $candidates) {
    throw "Inno Setup 6 was not found. Install it from https://jrsoftware.org/isinfo.php, then run this script again."
}

& $candidates $iss
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE."
}

Write-Host "Installer created in: $(Join-Path $root 'release')"