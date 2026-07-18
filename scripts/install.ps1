#Requires -Version 5.1
<#
.SYNOPSIS
  User-level installer for Deskline (no admin required).
#>
$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $ProjectRoot 'deskline\__main__.py'))) {
  $ProjectRoot = (Get-Location).Path
}

$InstallRoot = Join-Path $env:LOCALAPPDATA 'Programs\Deskline'
$VenvPython = Join-Path $InstallRoot 'venv\Scripts\python.exe'
$VenvPythonw = Join-Path $InstallRoot 'venv\Scripts\pythonw.exe'
$LauncherBat = Join-Path $InstallRoot 'Deskline.bat'
$LauncherVbs = Join-Path $InstallRoot 'Deskline.vbs'
$UninstallPs1 = Join-Path $InstallRoot 'uninstall.ps1'

Write-Host "Installing Deskline to $InstallRoot"

# Prefer Python 3.10 if available
$python = $null
$candidates = @(
  "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
  "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
  "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
  "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
)
foreach ($c in $candidates) {
  if (Test-Path $c) { $python = $c; break }
}
if (-not $python) {
  $python = (Get-Command python -ErrorAction SilentlyContinue | Select-Object -First 1).Source
}
if (-not $python) { throw 'Python was not found. Install Python 3.10+ and retry.' }

Write-Host "Using Python: $python"

New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null

# Fresh copy of app sources (keep existing venv if present)
$copyDirs = @('deskline', 'web')
foreach ($d in $copyDirs) {
  $src = Join-Path $ProjectRoot $d
  $dst = Join-Path $InstallRoot $d
  if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
  Copy-Item $src $dst -Recurse -Force
}
Copy-Item (Join-Path $ProjectRoot 'requirements.txt') (Join-Path $InstallRoot 'requirements.txt') -Force
Copy-Item (Join-Path $ProjectRoot 'pyproject.toml') (Join-Path $InstallRoot 'pyproject.toml') -Force
Copy-Item (Join-Path $ProjectRoot 'README.md') (Join-Path $InstallRoot 'README.md') -Force

if (-not (Test-Path $VenvPython)) {
  Write-Host 'Creating virtual environment...'
  & $python -m venv (Join-Path $InstallRoot 'venv')
}

Write-Host 'Installing dependencies...'
& $VenvPython -m pip install --upgrade pip -q
& $VenvPython -m pip install -r (Join-Path $InstallRoot 'requirements.txt') -q
& $VenvPython -m pip install -e $InstallRoot -q

# Console launcher
@"
@echo off
cd /d "%~dp0"
REM Prefer this install's package (.\deskline) over any other Deskline on the machine.
set "PYTHONPATH=%~dp0"
set "PYTHONNOUSERSITE=1"
if exist "%~dp0venv\Scripts\pythonw.exe" (
  start "" "%~dp0venv\Scripts\pythonw.exe" -m deskline
) else (
  start "" "%~dp0venv\Scripts\python.exe" -m deskline
)
"@ | Set-Content -Path $LauncherBat -Encoding ASCII

# Silent VBS launcher (no console flash)
@"
Set sh = CreateObject("WScript.Shell")
Dim fso, root
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = root
sh.Environment("PROCESS")("PYTHONPATH") = root
sh.Environment("PROCESS")("PYTHONNOUSERSITE") = "1"
exe = root & "\venv\Scripts\pythonw.exe"
If fso.FileExists(exe) = False Then
  exe = root & "\venv\Scripts\python.exe"
End If
sh.Run """" & exe & """ -m deskline", 0, False
"@ | Set-Content -Path $LauncherVbs -Encoding ASCII

# Bundled uninstaller
$uninstallContent = @'
$ErrorActionPreference = "Stop"
$InstallRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Get-Process pythonw,python -ErrorAction SilentlyContinue | Where-Object {
  $_.Path -and $_.Path.StartsWith($InstallRoot, [System.StringComparison]::OrdinalIgnoreCase)
} | Stop-Process -Force -ErrorAction SilentlyContinue
$desktop = [Environment]::GetFolderPath("Desktop")
$start = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$desktops = @(
  $desktop,
  (Join-Path $env:USERPROFILE "Desktop"),
  (Join-Path $env:USERPROFILE "OneDrive\Desktop")
) | Where-Object { $_ } | Select-Object -Unique
foreach ($d in $desktops) {
  Remove-Item (Join-Path $d "Deskline.lnk") -Force -ErrorAction SilentlyContinue
}
Remove-Item (Join-Path $start "Deskline.lnk") -Force -ErrorAction SilentlyContinue
Remove-Item $InstallRoot -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Deskline uninstalled."
'@
Set-Content -Path $UninstallPs1 -Value $uninstallContent -Encoding UTF8

function New-Shortcut {
  param(
    [string]$Path,
    [string]$Target,
    [string]$WorkDir,
    [string]$Description
  )
  try {
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) {
      New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $w = New-Object -ComObject WScript.Shell
    $s = $w.CreateShortcut($Path)
    $s.TargetPath = 'wscript.exe'
    $s.Arguments = '"' + $Target + '"'
    $s.WorkingDirectory = $WorkDir
    $s.WindowStyle = 7
    $s.Description = $Description
    $s.Save()
    return $true
  } catch {
    Write-Warning "Could not create shortcut: $Path ($($_.Exception.Message))"
    return $false
  }
}

$desktopCandidates = @(
  (Join-Path $env:USERPROFILE 'Desktop'),
  (Join-Path $env:USERPROFILE 'OneDrive\Desktop'),
  [Environment]::GetFolderPath('Desktop')
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
New-Shortcut -Path (Join-Path $startMenu 'Deskline.lnk') -Target $LauncherVbs -WorkDir $InstallRoot -Description 'Deskline local productivity tracker' | Out-Null

$desktopOk = $false
foreach ($desktop in $desktopCandidates) {
  if (New-Shortcut -Path (Join-Path $desktop 'Deskline.lnk') -Target $LauncherVbs -WorkDir $InstallRoot -Description 'Deskline local productivity tracker') {
    Write-Host "Desktop shortcut: $desktop\Deskline.lnk"
    $desktopOk = $true
    break
  }
}
if (-not $desktopOk) {
  Write-Warning 'Desktop shortcut was not created. Use Start Menu -> Deskline.'
}

Write-Host ''
Write-Host 'Deskline installed successfully.'
Write-Host "  Install dir : $InstallRoot"
Write-Host '  Start Menu  : Deskline'
Write-Host 'Launching Deskline...'
Start-Process -FilePath 'wscript.exe' -ArgumentList $LauncherVbs
