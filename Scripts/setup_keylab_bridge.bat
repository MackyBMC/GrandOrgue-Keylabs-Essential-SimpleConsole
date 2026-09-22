@echo off
title KeyLab - GrandOrgue bridge setup
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_keylab_bridge.ps1"
if errorlevel 1 (
  echo.
  echo Setup stopped with an error.
  pause
)