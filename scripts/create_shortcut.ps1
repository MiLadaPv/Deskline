#Requires -Version 5.1
$ErrorActionPreference = 'Stop'

$InstallRoot = Join-Path $env:LOCALAPPDATA 'Programs\Deskline'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LauncherVbs = Join-Path $InstallRoot 'Deskline.vbs'
$IconSrc = Join-Path $ProjectRoot 'assets\deskline.ico'
$IconDst = Join-Path $InstallRoot 'deskline.ico'

if (-not (Test-Path $LauncherVbs)) {
  throw "Deskline is not installed at $InstallRoot. Run scripts\install.ps1 first."
}

if (Test-Path $IconSrc) {
  Copy-Item $IconSrc $IconDst -Force
}

function New-DesklineShortcut {
  param([string]$Path, [string]$Icon)
  $dir = Split-Path -Parent $Path
  if ($dir -and -not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
  }
  $w = New-Object -ComObject WScript.Shell
  $s = $w.CreateShortcut($Path)
  $s.TargetPath = 'wscript.exe'
  $s.Arguments = '"' + $LauncherVbs + '"'
  $s.WorkingDirectory = $InstallRoot
  $s.WindowStyle = 7
  $s.Description = 'Deskline local productivity tracker'
  if ($Icon -and (Test-Path $Icon)) {
    $s.IconLocation = "$Icon,0"
  }
  $s.Save()
  Write-Host "Shortcut: $Path"
}

$icon = if (Test-Path $IconDst) { $IconDst } else { $null }

$desktopCandidates = New-Object System.Collections.Generic.List[string]
foreach ($p in @(
  (Join-Path $env:USERPROFILE 'Desktop'),
  (Join-Path $env:USERPROFILE 'OneDrive\Desktop'),
  [Environment]::GetFolderPath('Desktop')
)) {
  if ($p -and (Test-Path $p)) { [void]$desktopCandidates.Add($p) }
}

$od = Join-Path $env:USERPROFILE 'OneDrive'
if (Test-Path $od) {
  Get-ChildItem -LiteralPath $od -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $hasDeskline = Test-Path (Join-Path $_.FullName 'Deskline.lnk')
    $looksDesktop = $_.Name -like '*Desktop*' -or $_.Name -like '*desk*'
    if ($hasDeskline -or $looksDesktop) {
      [void]$desktopCandidates.Add($_.FullName)
    }
  }
}

$desktopCandidates = $desktopCandidates | Select-Object -Unique
foreach ($desktop in $desktopCandidates) {
  New-DesklineShortcut -Path (Join-Path $desktop 'Deskline.lnk') -Icon $icon
}

$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
New-DesklineShortcut -Path (Join-Path $startMenu 'Deskline.lnk') -Icon $icon

Write-Host 'Done. Double-click Deskline on the desktop to open.'
