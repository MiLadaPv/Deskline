@echo off
REM Deskline silent install helper — downloads latest Setup from GitHub and runs /VERYSILENT.
REM Silent installs do not auto-update. Re-run when a new version ships.
setlocal
set "PS1=%~dp0silent_install.ps1"
if not exist "%PS1%" set "PS1=%~dp0Deskline-SilentInstall.ps1"
if not exist "%PS1%" (
  echo silent_install.ps1 not found next to this .bat
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
exit /b %ERRORLEVEL%
