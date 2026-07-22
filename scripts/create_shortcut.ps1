#Requires -Version 5.1
$ErrorActionPreference = 'Continue'

$InstallRoot = Join-Path $env:LOCALAPPDATA 'Programs\Deskline'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LauncherVbs = Join-Path $InstallRoot 'Deskline.vbs'
$DesktopExe = Join-Path $InstallRoot 'deskline-desktop.exe'
$IconSrc = Join-Path $ProjectRoot 'assets\deskline.ico'
$IconDst = Join-Path $InstallRoot 'deskline.ico'

if (-not (Test-Path $LauncherVbs) -and -not (Test-Path $DesktopExe)) {
  throw "Deskline is not installed at $InstallRoot. Run scripts\install.ps1 first."
}

if (Test-Path $IconSrc) {
  Copy-Item $IconSrc $IconDst -Force
}

function New-DesklineShortcut {
  param([string]$Path, [string]$Icon)
  try {
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
      New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    if (Test-Path -LiteralPath $Path) {
      Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    }
    $w = New-Object -ComObject WScript.Shell
    $s = $w.CreateShortcut($Path)
    if (Test-Path -LiteralPath $DesktopExe) {
      $s.TargetPath = $DesktopExe
      $s.Arguments = ''
      $s.WorkingDirectory = $InstallRoot
      $s.WindowStyle = 1
    } else {
      $s.TargetPath = 'wscript.exe'
      $s.Arguments = '"' + $LauncherVbs + '"'
      $s.WorkingDirectory = $InstallRoot
      $s.WindowStyle = 7
    }
    $s.Description = 'Deskline local productivity tracker'
    if ($Icon -and (Test-Path -LiteralPath $Icon)) {
      $s.IconLocation = "$Icon,0"
    }
    $s.Save()
    Write-Host "Shortcut: $Path"
    return $true
  } catch {
    Write-Warning "Could not create shortcut: $Path ($($_.Exception.Message))"
    return $false
  }
}

$icon = if (Test-Path $IconDst) { $IconDst } else { $null }

$desktopCandidates = New-Object System.Collections.Generic.List[string]
foreach ($p in @(
  (Join-Path $env:USERPROFILE 'Desktop'),
  (Join-Path $env:USERPROFILE 'OneDrive\Desktop'),
  [Environment]::GetFolderPath('Desktop')
)) {
  if ($p -and (Test-Path -LiteralPath $p)) { [void]$desktopCandidates.Add($p) }
}

# Also pick OneDrive desktop folders with non-ASCII names (e.g. Russian "Рабочий стол")
$od = Join-Path $env:USERPROFILE 'OneDrive'
if (Test-Path -LiteralPath $od) {
  Get-ChildItem -LiteralPath $od -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $looksDesktop = $_.Name -match 'Desktop|desk|стол|Стол'
    $hasDeskline = Test-Path -LiteralPath (Join-Path $_.FullName 'Deskline.lnk')
    if ($looksDesktop -or $hasDeskline) {
      [void]$desktopCandidates.Add($_.FullName)
    }
  }
}

$desktopCandidates = $desktopCandidates | Select-Object -Unique
$ok = $false
foreach ($desktop in $desktopCandidates) {
  if (New-DesklineShortcut -Path (Join-Path $desktop 'Deskline.lnk') -Icon $icon) {
    $ok = $true
  }
}

$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
New-Item -ItemType Directory -Path $startMenu -Force | Out-Null
[void](New-DesklineShortcut -Path (Join-Path $startMenu 'Deskline.lnk') -Icon $icon)

if (-not $ok) {
  Write-Warning 'Desktop shortcut was not created. Use Start Menu -> Deskline.'
} else {
  Write-Host 'Done. Double-click Deskline on the desktop to open the app window.'
}