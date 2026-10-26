# One-off: build the clean development repo OUTSIDE the GrandOrgue folder, copying only what the bridge needs.
# Usage:  powershell -ExecutionPolicy Bypass -File setup_dev_repo.ps1 [-Source "H:\Users\bmche\Documents\GrandOrgue\Scripts"] [-Dest "C:\Work\github\GrandOrgue-Keylabs-Essential-SimpleConsole"]
# The source folder is only READ. Nothing in it is moved or deleted.
param(
  [string]$Source = "H:\Users\bmche\Documents\GrandOrgue\Scripts",
  [string]$Dest   = "C:\Work\github\GrandOrgue-Keylabs-Essential-SimpleConsole",
  [string]$Remote = "https://github.com/MackyBMC/GrandOrgue-Keylabs-Essential-SimpleConsole.git"
)
$kit = Split-Path -Parent $PSScriptRoot          # the unzipped v2 kit (this script lives in kit\tools)
New-Item -ItemType Directory -Force $Dest | Out-Null
# 1. kit (packaging, workflow, docs, tools, version, paths...)
robocopy $kit $Dest /E /XD __pycache__ .git dist build /NFL /NDL /NJH /NJS | Out-Null
# 2. the app itself, from the GrandOrgue Scripts folder (needed files only: the tidy tool's import graph decides)
$plan = python "$kit\tools\tidy_scripts_folder.py" $Source --list-needed
foreach ($rel in $plan) {
  $from = Join-Path $Source $rel
  $to   = Join-Path $Dest $rel
  New-Item -ItemType Directory -Force (Split-Path $to) | Out-Null
  Copy-Item $from $to -Force
}
foreach ($f in "config.yaml","README.md","LICENSE") { if (Test-Path "$Source\$f") { Copy-Item "$Source\$f" $Dest -Force } }
# kit versions of patched files win over the old ones
Copy-Item "$kit\keylab_go_bridge.py" $Dest -Force
Copy-Item "$kit\keylab_bridge\preset_store.py","$kit\keylab_bridge\paths.py" "$Dest\keylab_bridge" -Force
@"
__pycache__/
*.pyc
dist/
build/
.venv-build/
*.dist/
*.build/
*.onefile-build/
config.yaml
window_layout.json
takes/
"@ | Set-Content "$Dest\.gitignore"
# 3. git: reuse the existing repo history by cloning it, then dropping our files on top
if (-not (Test-Path "$Dest\.git")) { git -C $Dest init -b main; git -C $Dest remote add origin $Remote }
Write-Host "Dev repo ready: $Dest  (open it in VS Code; GrandOrgue folder is no longer your dev folder)"
