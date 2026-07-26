# Sign Deskline release binaries with Authenticode (OV/EV).
# Prerequisites: certificate in CurrentUser\My (or LocalMachine\My), Windows SDK signtool.
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\sign_release.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\sign_release.ps1 -Thumbprint ABCDEF...

param(
    [string]$Thumbprint = "",
    [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Find-SignTool {
    $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $kitRoot = "${env:ProgramFiles(x86)}\Windows Kits\10\bin"
    if (-not (Test-Path $kitRoot)) {
        throw "signtool.exe not found. Install Windows SDK Signing Tools, then reopen PowerShell."
    }
    $found = Get-ChildItem $kitRoot -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if (-not $found) {
        throw "signtool.exe not found under $kitRoot"
    }
    return $found.FullName
}

function Get-CodeSigningCerts {
    $stores = @(
        "Cert:\CurrentUser\My",
        "Cert:\LocalMachine\My"
    )
    $list = @()
    foreach ($store in $stores) {
        if (-not (Test-Path $store)) { continue }
        $list += Get-ChildItem $store -ErrorAction SilentlyContinue |
            Where-Object { $_.HasPrivateKey }
    }
    return $list
}

$signtool = Find-SignTool
Write-Host "signtool: $signtool"

$certs = @(Get-CodeSigningCerts)
if (-not $certs.Count) {
    Write-Host ""
    Write-Host "No certificates with a private key were found."
    Write-Host "1) Buy OV/EV Code Signing (see docs/SIGNING_BEGINNER.md)"
    Write-Host "2) Import the .pfx into Current User certificate store"
    Write-Host "3) Re-run this script"
    throw "No signing certificate available"
}

if ($Thumbprint) {
    $tp = ($Thumbprint -replace "\s", "").ToUpperInvariant()
    $cert = $certs | Where-Object { $_.Thumbprint.ToUpperInvariant() -eq $tp } | Select-Object -First 1
    if (-not $cert) { throw "Certificate thumbprint not found: $Thumbprint" }
} else {
    if ($certs.Count -gt 1) {
        Write-Host "Multiple certificates found — pick one with -Thumbprint:"
        $certs | ForEach-Object {
            Write-Host ("  {0}  {1}" -f $_.Thumbprint, $_.Subject)
        }
        throw "Pass -Thumbprint when more than one certificate exists"
    }
    $cert = $certs[0]
}

Write-Host ("Using cert: {0}" -f $cert.Subject)
Write-Host ("Thumbprint: {0}" -f $cert.Thumbprint)

$targets = @()
$setup = Get-ChildItem (Join-Path $Root "release\DesklineSetup-*.exe") -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if ($setup) {
    $targets += $setup.FullName
} else {
    throw "No release\DesklineSetup-*.exe — run scripts\prepare_release.ps1 first"
}

foreach ($extra in @(
    (Join-Path $Root "dist\Deskline\Deskline.exe"),
    (Join-Path $Root "dist\Deskline\deskline-desktop.exe")
)) {
    if (Test-Path $extra) { $targets += $extra }
}

foreach ($path in $targets) {
    Write-Host "Signing $path ..."
    & $signtool sign `
        /fd SHA256 `
        /td SHA256 `
        /tr $TimestampUrl `
        /sha1 $cert.Thumbprint `
        $path
    if ($LASTEXITCODE -ne 0) { throw "signtool sign failed for $path" }
    & $signtool verify /pa /v $path
    if ($LASTEXITCODE -ne 0) { throw "signtool verify failed for $path" }
}

# Refresh checksums for published Setup + extension zip
$OutDir = Join-Path $Root "release"
$lines = @()
Get-ChildItem $OutDir -File | Where-Object {
    $_.Name -like "DesklineSetup-*.exe" -or $_.Name -like "Deskline-Extension-*.zip"
} | ForEach-Object {
    $hash = (Get-FileHash -Algorithm SHA256 $_.FullName).Hash.ToLowerInvariant()
    $lines += "$hash  $($_.Name)"
}
$lines | Set-Content -Encoding ascii (Join-Path $OutDir "SHA256SUMS.txt")
Write-Host "Updated release\SHA256SUMS.txt"
Write-Host "Done. Next: upload to GitHub Releases (see docs/SIGNING_BEGINNER.md step 6)."
