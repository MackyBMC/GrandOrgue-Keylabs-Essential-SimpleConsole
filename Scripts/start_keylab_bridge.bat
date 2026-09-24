@echo off
title KeyLab - GrandOrgue bridge
cd /d "%~dp0"

if exist "build\keylab_go_bridge.exe" if not "%FORCE_PY%"=="1" goto compiled

set PY=python
where python >nul 2>nul || set PY=py

echo Starting the KeyLab - GrandOrgue bridge. Close this window or press Ctrl+C to stop.
echo.
%PY% keylab_go_bridge.py %*
goto finished

:compiled
echo Starting the compiled KeyLab - GrandOrgue bridge. Close this window or press Ctrl+C to stop.
echo.
build\keylab_go_bridge.exe %*

:finished

if errorlevel 1 (
  echo.
  echo The bridge stopped with an error - see the message above.
  echo If it says "No module named", run install_requirements.bat once.
  pause
)
