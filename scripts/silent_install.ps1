<#
.SYNOPSIS
  Download the latest DesklineSetup-*.exe from GitHub Releases and install silently.

.NOTES
  Silent installs do not auto-update. Re-run this script when a new version ships.
  Requires network access to api.github.com and github.com.
#>
[CmdletBinding()]
param(
    [string]$Repo = "MiLadaPv/Deskline",
    [string]$OutDir = $env:TEMP
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

Write-Host "Deskline silent install — fetching latest release from $Repo ..."
$headers = @{ "User-Agent" = "Deskline-SilentInstall" }
$rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers $headers
$asset = @($rel.assets) | Where-Object { $_.name -like "DesklineSetup-*.exe" } | Select-Object -First 1
if (-not $asset) {
    throw "No DesklineSetup-*.exe asset found on the latest GitHub release."
}

$dest = Join-Path $OutDir $asset.name
Write-Host "Downloading $($asset.name) ..."
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $dest -Headers $headers
Write-Host "Installing silently: $dest"
$p = Start-Process -FilePath $dest -ArgumentList "/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES" -Wait -PassThru
if ($p.ExitCode -ne 0) {
    throw "Installer exited with code $($p.ExitCode)"
}
Write-Host "Deskline installed. Launch from the Start menu or desktop shortcut."
