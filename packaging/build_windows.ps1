# Windows: build the program and the installer.   powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot)
python -m venv .venv-build
.\.venv-build\Scripts\python -m pip install -U pip -r requirements.txt -r requirements-build.txt
.\.venv-build\Scripts\python packaging\nuitka_build.py
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (Test-Path $iscc) { & $iscc packaging\installer.iss } else { Write-Warning "Inno Setup 6 not found: the program is in dist\keylab_go_bridge.dist" }
Get-ChildItem dist\installer\*.exe | ForEach-Object { "{0}  {1}" -f (Get-FileHash $_ -Algorithm SHA256).Hash, $_.Name } | Set-Content dist\installer\SHA256SUMS.txt
