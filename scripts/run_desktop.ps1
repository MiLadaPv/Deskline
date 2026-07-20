# Build and run Deskline as a Tauri desktop app.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Desktop = Join-Path $Root "deskline-desktop"

Set-Location $Desktop
if (-not (Test-Path (Join-Path $Desktop "node_modules"))) {
  npm install
}

Write-Host "Starting Deskline desktop (Tauri dev)..."
npm run dev
