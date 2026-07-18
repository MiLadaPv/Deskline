@echo off
cd /d "%~dp0"
REM Prefer this install's package (.\deskline) over any other Deskline on the machine.
set "PYTHONPATH=%~dp0"
set "PYTHONNOUSERSITE=1"
if exist "%~dp0venv\Scripts\pythonw.exe" (
  start "" "%~dp0venv\Scripts\pythonw.exe" -m deskline
) else (
  start "" "%~dp0venv\Scripts\python.exe" -m deskline
)
