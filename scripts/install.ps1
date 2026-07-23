#Requires -Version 5.1
<#
.SYNOPSIS
  User-level installer for Deskline (no admin required).
  Installs Python backend + native Tauri shell; desktop shortcut launches deskline-desktop.exe only.
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
$DesktopExeName = 'deskline-desktop.exe'
$DesktopExeDst = Join-Path $InstallRoot $DesktopExeName

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

# Native desktop shell (required for shortcuts)
$desktopCandidates = @(
  (Join-Path $ProjectRoot 'deskline-desktop\src-tauri\target\release\deskline-desktop.exe'),
  (Join-Path $ProjectRoot 'deskline-desktop\src-tauri\target\debug\deskline-desktop.exe'),
  $DesktopExeDst
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

$desktopSrc = $desktopCandidates | Select-Object -First 1
if (-not $desktopSrc) {
  Write-Warning @"
deskline-desktop.exe was not found.
Build it first:
  cd deskline-desktop
  npm install
  npm run build
Then re-run this installer.
"@
  throw "Missing $DesktopExeName — build the Tauri shell before install."
}

if ($desktopSrc -ne $DesktopExeDst) {
  Copy-Item $desktopSrc $DesktopExeDst -Force
  Write-Host "Copied desktop shell: $DesktopExeDst"
} else {
  Write-Host "Desktop shell already in place: $DesktopExeDst"
}

if (-not (Test-Path $VenvPython)) {
  Write-Host 'Creating virtual environment...'
  & $python -m venv (Join-Path $InstallRoot 'venv')
}

Write-Host 'Installing dependencies...'
& $VenvPython -m pip install --upgrade pip -q
& $VenvPython -m pip install -r (Join-Path $InstallRoot 'requirements.txt') -q
& $VenvPython -m pip install -e $InstallRoot -q

# Console launcher — desktop exe only (no silent tray fallback)
@"
@echo off
cd /d "%~dp0"
if not exist "%~dp0deskline-desktop.exe" (
  echo Deskline desktop shell is missing: deskline-desktop.exe
  echo Re-run install.bat after building deskline-desktop ^(npm run build^).
  pause
  exit /b 1
)
start "" "%~dp0deskline-desktop.exe"
"@ | Set-Content -Path $LauncherBat -Encoding ASCII

# Silent VBS launcher — desktop exe only; MessageBox if missing
@"
Set sh = CreateObject("WScript.Shell")
Dim fso, root, desktopExe
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = root
desktopExe = root & "\deskline-desktop.exe"
If fso.FileExists(desktopExe) Then
  sh.Run """" & desktopExe & """", 1, False
  WScript.Quit 0
End If
MsgBox "Deskline desktop shell is missing:" & vbCrLf & desktopExe & vbCrLf & vbCrLf & _
  "Re-run install.bat after building deskline-desktop (npm run build)." & vbCrLf & _
  "Log: %LOCALAPPDATA%\Deskline\desktop.log", 16, "Deskline"
WScript.Quit 1
"@ | Set-Content -Path $LauncherVbs -Encoding ASCII

# Bundled uninstaller
$uninstallContent = @'
$ErrorActionPreference = "Stop"
$InstallRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Get-Process deskline-desktop,pythonw,python -ErrorAction SilentlyContinue | Where-Object {
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
    [string]$Description,
    [string]$IconPath = $null,
    [string]$Arguments = ''
  )
  try {
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) {
      New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $w = New-Object -ComObject WScript.Shell
    $s = $w.CreateShortcut($Path)
    $s.TargetPath = $Target
    $s.Arguments = $Arguments
    $s.WorkingDirectory = $WorkDir
    $s.WindowStyle = 1
    $s.Description = $Description
    if ($IconPath -and (Test-Path $IconPath)) {
      $s.IconLocation = "$IconPath,0"
    }
    $s.Save()
    return $true
  } catch {
    Write-Warning "Could not create shortcut: $Path ($($_.Exception.Message))"
    return $false
  }
}

$iconSrc = Join-Path $ProjectRoot 'assets\deskline.ico'
$iconDst = Join-Path $InstallRoot 'deskline.ico'
if (Test-Path $iconSrc) {
  Copy-Item $iconSrc $iconDst -Force
}

$shortcutDesktops = @(
  (Join-Path $env:USERPROFILE 'Desktop'),
  (Join-Path $env:USERPROFILE 'OneDrive\Desktop'),
  [Environment]::GetFolderPath('Desktop')
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
New-Item -ItemType Directory -Path $startMenu -Force | Out-Null

# Prefer direct link to native shell (no wscript indirection)
$shortcutTarget = $DesktopExeDst
$shortcutArgs = ''
if (-not (Test-Path $shortcutTarget)) {
  $shortcutTarget = 'wscript.exe'
  $shortcutArgs = '"' + $LauncherVbs + '"'
}

New-Shortcut -Path (Join-Path $startMenu 'Deskline.lnk') -Target $shortcutTarget -Arguments $shortcutArgs -WorkDir $InstallRoot -Description 'Deskline local productivity tracker' -IconPath $iconDst | Out-Null

$desktopOk = $false
foreach ($desktop in $shortcutDesktops) {
  if (New-Shortcut -Path (Join-Path $desktop 'Deskline.lnk') -Target $shortcutTarget -Arguments $shortcutArgs -WorkDir $InstallRoot -Description 'Deskline local productivity tracker' -IconPath $iconDst) {
    Write-Host "Desktop shortcut: $desktop\Deskline.lnk"
    $desktopOk = $true
  }
}
if (-not $desktopOk) {
  Write-Warning 'Desktop shortcut was not created. Use Start Menu -> Deskline.'
}

Write-Host ''
Write-Host 'Deskline installed successfully.'
Write-Host "  Install dir : $InstallRoot"
Write-Host "  Desktop exe : $DesktopExeDst"
Write-Host '  Start Menu  : Deskline'
Write-Host 'Launching Deskline...'
Start-Process -FilePath $DesktopExeDst
