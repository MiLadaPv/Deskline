# Prefer a built Deskline desktop EXE; otherwise run Tauri in dev mode.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Desktop = Join-Path $Root "deskline-desktop"
$ReleaseExe = Join-Path $Desktop "src-tauri\target\release\deskline-desktop.exe"
$InstallExe = Join-Path $env:LOCALAPPDATA "Programs\Deskline\deskline-desktop.exe"

if (Test-Path $ReleaseExe) {
  Write-Host "Starting built Deskline desktop: $ReleaseExe"
  Start-Process -FilePath $ReleaseExe
  exit 0
}
if (Test-Path $InstallExe) {
  Write-Host "Starting installed Deskline desktop: $InstallExe"
  Start-Process -FilePath $InstallExe
  exit 0
}

Set-Location $Desktop
if (-not (Test-Path (Join-Path $Desktop "node_modules"))) {
  npm install
}

Write-Host "Starting Deskline desktop (Tauri dev)..."
npm run dev
