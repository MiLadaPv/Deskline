@echo off
REM Quick launch from the project folder (development / without installer)
setlocal
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (
  echo Python not found.
  pause
  exit /b 1
)
start "" pythonw -m deskline
if errorlevel 1 start "" python -m deskline
endlocal
