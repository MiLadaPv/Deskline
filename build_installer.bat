@echo off
setlocal
cd /d "%~dp0"
echo Building full Windows installer (this may take several minutes)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_installer.ps1"
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)
explorer "%~dp0release"
echo.
echo Open the DesklineSetup-*.exe in the release folder to install.
pause
endlocal
