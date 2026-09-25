@echo off
title KeyLab bridge - install requirements

:: Check for LoopMIDI and open download page if not found
where loopmidi >nul 2>nul || (
    echo [!] LoopMIDI is required but not installed.
    echo     Opening LoopMIDI download page...
    start https://www.tobias-erichsen.de/software/loopmidi.html
)

:: Check for GrandOrgue and open download page if not found
where grandorgue >nul 2>nul || (
    echo [!] GrandOrgue is required but not installed.
    echo     Opening GrandOrgue download page...
    start https://github.com/GrandOrgue/grandorgue
)

:: Install Python dependencies
set PY=python
where python >nul 2>nul || set PY=py
%PY% -m pip install --upgrade mido python-rtmidi pyyaml

echo.
pause

