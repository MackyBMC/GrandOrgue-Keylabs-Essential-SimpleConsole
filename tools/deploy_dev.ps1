<#
  deploy_dev.ps1  -  DEV ONLY (not for end users, not for GitHub as an installer)
  Copies the program from the dev repo to the live GrandOrgue Scripts folder.

  Run (any of these; the script re-launches itself with the execution policy bypassed, so no policy change is needed):
      powershell -NoProfile -ExecutionPolicy Bypass -File C:\Work\Github\GrandOrgue-Keylabs-Essential-SimpleConsole\tools\deploy_dev.ps1
      .\deploy_dev.ps1 -Preview        # show what would be copied, change nothing
            .\deploy_dev.ps1 -Pip            # install requirements into the deployed .venv-build
            .\deploy_dev.ps1 -Run            # start the bridge with the deployed .venv-build Python
      .\deploy_dev.ps1 -IncludeData    # also copy Combinations / Settings starter files (only files that do not exist yet)

  Never overwritten in the live folder: config.yaml, theme.txt, language.txt, go_folder.txt, last_dirs.json,
  preset_activation.txt, midi\, Combinations\, Settings\ (your real data). config.yaml is copied only if missing.

  CHANGELOG
    2026-11-10  Preserve deployed venvs; -Pip targets .venv-build and -Run uses that interpreter.
  2026-11-09  New.
#>
[CmdletBinding()]
param(
    [string]$Source = "C:\Work\Github\GrandOrgue-Keylabs-Essential-SimpleConsole",
    [string]$Target = "H:\Users\bmche\Documents\GrandOrgue\Scripts",
    [switch]$Preview,
    [switch]$Pip,
    [switch]$Run,
    [switch]$IncludeData,
    [switch]$NoBackup
)

# ---- script-blocking overrides: relaunch once with policy bypassed, and unblock downloaded files
if (-not $env:KEYLAB_DEPLOY_BYPASS) {
    $env:KEYLAB_DEPLOY_BYPASS = "1"
    try { Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force -ErrorAction Stop } catch {}
    try { Get-ChildItem -LiteralPath $PSScriptRoot -Filter *.ps1 -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue } catch {}
    $argList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"")
    foreach ($entry in $PSBoundParameters.GetEnumerator()) {
        if ($entry.Value -is [System.Management.Automation.SwitchParameter]) { if ($entry.Value) { $argList += "-$($entry.Key)" } }
        else { $argList += "-$($entry.Key)"; $argList += "`"$($entry.Value)`"" }
    }
    $exe = (Get-Process -Id $PID).Path
    & $exe @argList
    exit $LASTEXITCODE
}

$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath (Join-Path $Source "keylab_go_bridge.py"))) { throw "Source is not the repo: $Source" }
if (-not (Test-Path -LiteralPath $Target)) { New-Item -ItemType Directory -Path $Target -Force | Out-Null }
$Source = (Resolve-Path -LiteralPath $Source).Path
$Target = (Resolve-Path -LiteralPath $Target).Path
if ($Source -eq $Target) { throw "Source and target are the same folder." }
$TargetPython = Join-Path $Target ".venv-build\Scripts\python.exe"

# ---- backup of the code files about to be replaced
if (-not $NoBackup -and -not $Preview) {
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupDir = Join-Path (Split-Path $Target -Parent) "Scripts_backup"
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    $zip = Join-Path $backupDir "Scripts_$stamp.zip"
    $items = Get-ChildItem -LiteralPath $Target -Force | Where-Object { $_.Name -notin @("Combinations", "Settings", "midi", "__pycache__") }
    if ($items) { Compress-Archive -LiteralPath $items.FullName -DestinationPath $zip -Force; Write-Host "Backup: $zip" -ForegroundColor DarkGray }
    Get-ChildItem -LiteralPath $backupDir -Filter "Scripts_*.zip" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 10 | Remove-Item -Force   # keep the last 10
}

# ---- copy code (no deletions, personal data excluded)
$excludeDirs = @(".git", ".github", ".kilo", ".vscode", ".venv", ".venv-build", "__pycache__", "workings", "docs", "packaging", "tools", "dist", "build", "midi", "Organs")
$excludeFiles = @("config.yaml", "theme.txt", "language.txt", "go_folder.txt", "last_dirs.json", "preset_activation.txt",
                  "*.patch", "*.pyc", "*.md", "LICENSE", ".gitignore", "requirements-build.txt")
if (-not $IncludeData) { $excludeDirs += @("Combinations", "Settings") }
$flags = @("/E", "/R:1", "/W:1", "/NP", "/NJH", "/NDL", "/XO")        # /XO: never replace a newer file in the live folder
if ($Preview) { $flags += "/L" }
$roboArgs = @($Source, $Target) + $flags + @("/XD") + $excludeDirs + @("/XF") + $excludeFiles
& robocopy @roboArgs
if ($LASTEXITCODE -ge 8) { throw "robocopy failed (exit $LASTEXITCODE)" }

# ---- data starters: only files that do not exist yet
if ($IncludeData) {
    foreach ($folder in @("Combinations", "Settings")) {
        $from = Join-Path $Source $folder
        if (Test-Path -LiteralPath $from) {
            $dataArgs = @($from, (Join-Path $Target $folder), "/E", "/XC", "/XN", "/XO", "/R:1", "/W:1", "/NP", "/NJH", "/NDL")
            if ($Preview) { $dataArgs += "/L" }
            & robocopy @dataArgs | Out-Null
        }
    }
}

# ---- config.yaml: only when the live folder has none
$liveConfig = Join-Path $Target "config.yaml"
if (-not (Test-Path -LiteralPath $liveConfig) -and (Test-Path -LiteralPath (Join-Path $Source "config.yaml"))) {
    if ($Preview) { Write-Host "(preview) would copy config.yaml" } else { Copy-Item -LiteralPath (Join-Path $Source "config.yaml") -Destination $liveConfig; Write-Host "config.yaml copied (none existed)" }
}

if ($Preview) { Write-Host "Preview only: nothing was changed." -ForegroundColor Yellow; exit 0 }

# ---- clear stale bytecode so the new code is what runs
Get-ChildItem -LiteralPath $Target -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

if ($Pip) {
    if (-not (Test-Path -LiteralPath $TargetPython)) { throw "Target Python venv not found: $TargetPython" }
    $req = Join-Path $Source "requirements.txt"
    if (-not (Test-Path -LiteralPath $req)) { throw "Requirements file not found: $req" }
    $PipPython = Join-Path $Source ".venv-build\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $PipPython)) {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCommand) { throw "A working Python with pip is needed to install into $TargetPython" }
        $PipPython = $pythonCommand.Source
    }
    & $PipPython -m pip --python $TargetPython install -r $req
    if ($LASTEXITCODE -ne 0) { throw "pip install failed (exit $LASTEXITCODE) into $TargetPython" }
}

Write-Host "Deployed $Source -> $Target" -ForegroundColor Green
if ($Run) {
    if (-not (Test-Path -LiteralPath $TargetPython)) { throw "Target Python venv not found: $TargetPython" }
    Push-Location $Target
    try { & $TargetPython keylab_go_bridge.py } finally { Pop-Location }
}
