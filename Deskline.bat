@echo off
REM Deskline — native desktop window (Tauri). No silent tray-only fallback.
setlocal
cd /d "%~dp0"

set "RELEASE_EXE=%~dp0deskline-desktop\src-tauri\target\release\deskline-desktop.exe"
set "INSTALL_EXE=%LOCALAPPDATA%\Programs\Deskline\deskline-desktop.exe"

if exist "%RELEASE_EXE%" (
  start "" "%RELEASE_EXE%"
  exit /b 0
)
if exist "%INSTALL_EXE%" (
  start "" "%INSTALL_EXE%"
  exit /b 0
)

where powershell >nul 2>&1
if not errorlevel 1 (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_desktop.ps1"
  if not errorlevel 1 exit /b 0
)

echo.
echo Deskline desktop shell was not found.
echo.
echo Build it:
echo   cd deskline-desktop
echo   npm install
echo   npm run build
echo.
echo Or run install.bat after a successful build.
echo Log: %%LOCALAPPDATA%%\Deskline\desktop.log
echo.
pause
exit /b 1
