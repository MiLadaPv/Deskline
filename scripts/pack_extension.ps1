# Pack Deskline Chrome extension for Web Store / GitHub Releases.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\pack_extension.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Ext = Join-Path $Root "extension"
$ManifestPath = Join-Path $Ext "manifest.json"
if (-not (Test-Path $ManifestPath)) {
    throw "Missing $ManifestPath"
}

$manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json
$ver = [string]$manifest.version
if (-not $ver) { throw "manifest.json has no version" }

$OutDir = Join-Path $Root "release"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$ZipName = "Deskline-Extension-$ver.zip"
$ZipPath = Join-Path $OutDir $ZipName
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }

$stage = Join-Path $env:TEMP ("deskline-ext-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $stage | Out-Null
try {
    $include = @(
        "manifest.json",
        "background.js",
        "popup.html",
        "popup.js",
        "popup.css",
        "download.html",
        "icons"
    )
    foreach ($name in $include) {
        $src = Join-Path $Ext $name
        if (-not (Test-Path $src)) { throw "Missing extension file: $name" }
        Copy-Item -Recurse -Force $src (Join-Path $stage $name)
    }
    Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $ZipPath -Force
} finally {
    Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
}

Write-Host "Wrote $ZipPath"
Get-FileHash -Algorithm SHA256 $ZipPath | Format-List
