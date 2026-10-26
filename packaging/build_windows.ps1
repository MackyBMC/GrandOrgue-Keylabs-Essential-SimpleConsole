# Windows: build the program and the installer.
#   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1              (full build)
#   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1 -InstallerOnly   (reuse dist\keylab_go_bridge.dist, just compile the installer)
param([switch]$InstallerOnly)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot)
if (-not $InstallerOnly) {
  python -m venv .venv-build
  .\.venv-build\Scripts\python -m pip install -U pip -r requirements.txt -r requirements-build.txt
  .\.venv-build\Scripts\python packaging\nuitka_build.py
}
if (-not (Test-Path "dist\keylab_go_bridge.dist\KeyLabGrandOrgueBridge.exe")) { throw "Program build missing: run without -InstallerOnly first." }
$python = ".venv-build\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Build Python not found: $python" }
$appVersion = & $python -c "from version import APP_VERSION; print(APP_VERSION)"
if ($LASTEXITCODE -ne 0 -or -not $appVersion) { throw "Could not read APP_VERSION from version.py." }
$iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue; if ($cmd) { $iscc = $cmd.Source } }
if (-not $iscc) { Write-Warning "Inno Setup 6 not found. Install it:  winget install JRSoftware.InnoSetup   then run again with -InstallerOnly"; exit 1 }
& $iscc "/DAppVersion=$appVersion" packaging\installer.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }
Get-ChildItem dist\installer\*.exe | ForEach-Object { "{0}  {1}" -f (Get-FileHash $_ -Algorithm SHA256).Hash, $_.Name } | Set-Content dist\installer\SHA256SUMS.txt
Write-Host "Done: dist\installer"
