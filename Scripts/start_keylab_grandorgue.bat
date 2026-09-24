@echo off
title KeyLab - GrandOrgue
cd /d "%~dp0"

set "PS_SCRIPT=%~dp0start_keylab_grandorgue.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"

if errorlevel 1 (
  echo.
  echo GrandOrgue startup failed - see the message above.
  pause
)