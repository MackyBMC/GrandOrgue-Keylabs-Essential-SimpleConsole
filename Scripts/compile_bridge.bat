@echo off
title Compile keylab_go_bridge.py with Nuitka
cd /d "%~dp0"

REM What this actually buys you: Nuitka compiles Python to C, then to a native .exe.
REM That genuinely speeds up CPU-bound code and cuts interpreter startup time.
REM It does NOT reduce MIDI/USB I/O latency - waiting on a message from the keyboard
REM takes exactly as long either way. The --relay-main callback design (not this
REM compile step) is what actually removes the polling-loop delay. Use both if you
REM like; don't expect this alone to fix latency.
REM
REM Needs a C compiler. Easiest on Windows: let Nuitka fetch a private MinGW64 for
REM you (below) - no Visual Studio install required, but the first run downloads
REM ~100 MB and can take several minutes.

set PY=python
where python >nul 2>nul || set PY=py

echo Installing Nuitka (first run only; safe to re-run)...
%PY% -m pip install --upgrade nuitka ordered-set >nul
if errorlevel 1 (
  echo pip install failed - run install_requirements.bat first.
  pause
  exit /b 1
)

echo.
echo Compiling... this can take a few minutes the first time.
%PY% -m nuitka --standalone --onefile --assume-yes-for-downloads ^
  --onefile-no-compression ^
  --windows-console-mode=force ^
  --include-package=mido.backends.rtmidi ^
  --include-package=rtmidi ^
  --output-filename=keylab_go_bridge.exe ^
  --output-dir=build ^
  keylab_go_bridge.py

if errorlevel 1 (
  echo.
  echo Compile failed - see the messages above.
  pause
  exit /b 1
)

echo.
echo Done: build\keylab_go_bridge.exe
echo start_keylab_bridge.bat / .ps1 now use this automatically, since it sits in build\.
echo config.yaml stays where it is - the exe reads it the same way the script does.
echo To go back to the Python script instead, set FORCE_PY=1 before running the launcher,
echo or just delete the build\ folder.
pause
