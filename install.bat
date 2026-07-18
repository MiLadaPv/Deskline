@echo off
setlocal
cd /d "%~dp0"
echo Installing Deskline...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
if errorlevel 1 (
  echo Install failed.
  pause
  exit /b 1
)
echo.
echo Done. Use the Deskline desktop shortcut or Start Menu item to launch.
pause
endlocal
