@echo off
REM Deskline — native desktop window (Tauri). Falls back to tray+API only if desktop unavailable.
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
if errorlevel 1 goto :python_fallback

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run_desktop.ps1"
if errorlevel 1 goto :python_fallback
exit /b 0

:python_fallback
echo Desktop shell unavailable — starting tracker in tray (no browser).
where pythonw >nul 2>&1
if not errorlevel 1 (
  start "" pythonw -m deskline --no-browser
  exit /b 0
)
where python >nul 2>&1
if not errorlevel 1 (
  start "" python -m deskline --no-browser
  exit /b 0
)
echo Python not found. Install Python or build deskline-desktop (npm run build).
pause
exit /b 1
