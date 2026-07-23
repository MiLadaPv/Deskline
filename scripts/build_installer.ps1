#Requires -Version 5.1
<#
.SYNOPSIS
  Build Windows Setup.exe: PyInstaller backend + Tauri deskline-desktop.exe shell.
#>
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$DesktopDir = Join-Path $Root 'deskline-desktop'
$DesktopExe = Join-Path $DesktopDir 'src-tauri\target\release\deskline-desktop.exe'

Write-Host '== Building deskline-desktop.exe (Tauri) =='
if (-not (Test-Path (Join-Path $DesktopDir 'package.json'))) {
  throw "Missing deskline-desktop at $DesktopDir"
}
Push-Location $DesktopDir
try {
  if (-not (Test-Path (Join-Path $DesktopDir 'node_modules'))) {
    npm install
  }
  npm run build
} finally {
  Pop-Location
}
if (-not (Test-Path $DesktopExe)) {
  throw "Tauri build failed: $DesktopExe not found"
}

Write-Host '== Building Deskline.exe (PyInstaller backend) =='
python -m pip install -q pyinstaller pillow mss fastapi uvicorn jinja2 python-multipart pywin32 pystray
if (Test-Path "$Root\dist\Deskline") { Remove-Item "$Root\dist\Deskline" -Recurse -Force }
if (Test-Path "$Root\build") { Remove-Item "$Root\build" -Recurse -Force }

python -m PyInstaller --noconfirm --clean deskline.spec
if (-not (Test-Path "$Root\dist\Deskline\Deskline.exe")) {
  throw 'PyInstaller failed: Deskline.exe not found'
}

# Stage Tauri shell next to the frozen backend so Inno ships one folder
Copy-Item $DesktopExe (Join-Path $Root 'dist\Deskline\deskline-desktop.exe') -Force
Write-Host "Staged deskline-desktop.exe into dist\Deskline\"

$iscc = @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
  "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) { throw 'Inno Setup ISCC.exe not found. Install Inno Setup 6.' }

Write-Host "== Compiling installer with $iscc =="
New-Item -ItemType Directory -Path "$Root\release" -Force | Out-Null
& $iscc "$Root\installer\deskline.iss"
if ($LASTEXITCODE -ne 0) { throw "ISCC failed with code $LASTEXITCODE" }

$setup = Get-ChildItem "$Root\release\DesklineSetup-*.exe" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Host ''
Write-Host "Installer ready: $($setup.FullName)"
Write-Host "Size: $([math]::Round($setup.Length/1MB, 1)) MB"
Write-Host 'Shortcuts launch deskline-desktop.exe (native window).'
