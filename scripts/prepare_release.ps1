# Prepare release artifacts (unsigned). Sign per docs/SIGNING.md before publishing.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\prepare_release.ps1 [-SkipInstaller]

param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$ver = (python -c "from deskline import __version__; print(__version__)").Trim()
Write-Host "Deskline version $ver"

Write-Host "Running tests..."
python -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }

Write-Host "Packing extension..."
powershell -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\pack_extension.ps1")

$OutDir = Join-Path $Root "release"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

if (-not $SkipInstaller) {
    $build = Join-Path $Root "scripts\build_installer.ps1"
    if (Test-Path $build) {
        Write-Host "Building installer..."
        powershell -ExecutionPolicy Bypass -File $build
    } else {
        Write-Warning "build_installer.ps1 not found — skip Setup.exe"
    }
}

$checksums = Join-Path $OutDir "SHA256SUMS.txt"
$lines = @()
Get-ChildItem $OutDir -File | Where-Object {
    $_.Name -like "DesklineSetup-*.exe" -or $_.Name -like "Deskline-Extension-*.zip"
} | ForEach-Object {
    $hash = (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLowerInvariant()
    $lines += "$hash  $($_.Name)"
    Write-Host "$($_.Name)  $hash"
}
$lines | Set-Content -Encoding ascii $checksums
Write-Host "Wrote $checksums"
Write-Host ""
Write-Host "Next: sign binaries (docs/SIGNING.md), then:"
Write-Host "  gh release create v$ver release/DesklineSetup-$ver.exe release/Deskline-Extension-$ver.zip release/SHA256SUMS.txt -F docs/RELEASE_NOTES.template.md"
