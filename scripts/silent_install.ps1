# Download the latest DesklineSetup-*.exe from GitHub Releases and install silently.
# Silent installs do not auto-update. Re-run when a new version ships.
[CmdletBinding()]
param(
    [string]$Repo = "MiLadaPv/Deskline",
    [string]$OutDir = $env:TEMP
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

Write-Host "Deskline silent install - fetching latest release from $Repo ..."
$headers = @{ "User-Agent" = "Deskline-SilentInstall" }
try {
    $rel = Invoke-RestMethod -Uri "https://api.github.com/repos/$Repo/releases/latest" -Headers $headers
} catch {
    Write-Host "ERROR: No published GitHub release found for $Repo."
    Write-Host "Publish a release with DesklineSetup-*.exe, then re-run this script."
    Write-Host "Releases: https://github.com/$Repo/releases"
    Write-Host $_.Exception.Message
    exit 2
}

$asset = @($rel.assets) | Where-Object { $_.name -like "DesklineSetup-*.exe" } | Select-Object -First 1
if (-not $asset) {
    Write-Host "ERROR: Latest release '$($rel.tag_name)' has no DesklineSetup-*.exe asset."
    Write-Host "Attach the Setup from scripts/prepare_release.ps1, then re-run."
    Write-Host "Releases: https://github.com/$Repo/releases"
    exit 3
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
