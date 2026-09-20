@echo off
title KeyLab bridge - install requirements
set PY=python
where python >nul 2>nul || set PY=py
%PY% -m pip install --upgrade mido python-rtmidi pyyaml
echo.
pause
