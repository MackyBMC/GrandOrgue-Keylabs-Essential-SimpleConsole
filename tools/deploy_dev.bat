@echo off
rem Double-click launcher for deploy_dev.ps1 (policy bypass). Pass switches after the name, e.g. deploy_dev.bat -Preview
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy_dev.ps1" %*
pause
