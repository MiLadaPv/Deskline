#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host '== Building Deskline.exe (PyInstaller) =='
python -m pip install -q pyinstaller pillow mss fastapi uvicorn jinja2 python-multipart pywin32 pystray
if (Test-Path "$Root\dist\Deskline") { Remove-Item "$Root\dist\Deskline" -Recurse -Force }
if (Test-Path "$Root\build") { Remove-Item "$Root\build" -Recurse -Force }

python -m PyInstaller --noconfirm --clean deskline.spec
if (-not (Test-Path "$Root\dist\Deskline\Deskline.exe")) {
  throw 'PyInstaller failed: Deskline.exe not found'
}

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
