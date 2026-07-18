#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
$InstallRoot = Join-Path $env:LOCALAPPDATA 'Programs\Deskline'
$Uninstall = Join-Path $InstallRoot 'uninstall.ps1'
if (Test-Path $Uninstall) {
  & powershell -NoProfile -ExecutionPolicy Bypass -File $Uninstall
} elseif (Test-Path $InstallRoot) {
  Get-Process pythonw,python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -and $_.Path.StartsWith($InstallRoot, [System.StringComparison]::OrdinalIgnoreCase)
  } | Stop-Process -Force -ErrorAction SilentlyContinue
  $start = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
  $desktops = @(
    [Environment]::GetFolderPath('Desktop'),
    (Join-Path $env:USERPROFILE 'Desktop'),
    (Join-Path $env:USERPROFILE 'OneDrive\Desktop')
  ) | Where-Object { $_ } | Select-Object -Unique
  foreach ($d in $desktops) {
    Remove-Item (Join-Path $d 'Deskline.lnk') -Force -ErrorAction SilentlyContinue
  }
  Remove-Item (Join-Path $start 'Deskline.lnk') -Force -ErrorAction SilentlyContinue
  Remove-Item $InstallRoot -Recurse -Force
  Write-Host 'Deskline removed.'
} else {
  Write-Host 'Deskline is not installed.'
}
