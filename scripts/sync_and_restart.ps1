# Sync project -> install and hard-restart a single Deskline instance.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\sync_and_restart.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$InstallRoot = Join-Path $env:LOCALAPPDATA "Programs\Deskline"
$Port = 8787

Write-Host "Project: $ProjectRoot"
Write-Host "Install: $InstallRoot"

function Stop-DesklineProcesses {
  $killed = 0
  Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
      $_.CommandLine -and (
        $_.CommandLine -match '-m\s+deskline' -or
        $_.CommandLine -match 'deskline_app\.py' -or
        ($_.Name -match 'pythonw?\.exe' -and $_.CommandLine -match 'Deskline')
      )
    } |
    ForEach-Object {
      Write-Host "Stopping PID $($_.ProcessId): $($_.Name)"
      Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
      $killed++
    }
  Start-Sleep -Seconds 1
  Write-Host "Stopped $killed Deskline process(es)."
}

function Sync-Install {
  if (-not (Test-Path $InstallRoot)) {
    throw "Install root missing: $InstallRoot (run install.ps1 first)"
  }
  foreach ($name in @("deskline", "web", "scripts")) {
    $from = Join-Path $ProjectRoot $name
    $to = Join-Path $InstallRoot $name
    if (-not (Test-Path $from)) { continue }
    Write-Host "Sync $name -> $to"
    if (-not (Test-Path $to)) {
      New-Item -ItemType Directory -Path $to -Force | Out-Null
    }
    robocopy $from $to /E /XD __pycache__ .pytest_cache /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    if ($LASTEXITCODE -ge 8) {
      throw "robocopy failed for $name with code $LASTEXITCODE"
    }
  }
  foreach ($f in @("pyproject.toml", "requirements.txt")) {
    $src = Join-Path $ProjectRoot $f
    if (Test-Path $src) {
      Copy-Item $src (Join-Path $InstallRoot $f) -Force
    }
  }
}

function Start-Deskline {
  $pythonw = Join-Path $InstallRoot "venv\Scripts\pythonw.exe"
  $python = Join-Path $InstallRoot "venv\Scripts\python.exe"
  if (Test-Path $pythonw) {
    Start-Process -FilePath $pythonw -ArgumentList "-m","deskline","--no-browser" -WorkingDirectory $InstallRoot
  } elseif (Test-Path $python) {
    Start-Process -FilePath $python -ArgumentList "-m","deskline","--no-browser" -WorkingDirectory $InstallRoot
  } else {
    throw "No venv python in $InstallRoot"
  }
}

function Wait-Port {
  param([int]$Seconds = 25)
  for ($i = 0; $i -lt $Seconds; $i++) {
    try {
      $c = New-Object System.Net.Sockets.TcpClient
      $c.Connect("127.0.0.1", $Port)
      $c.Close()
      return $true
    } catch {
      Start-Sleep -Seconds 1
    }
  }
  return $false
}

function Assert-SummaryHealthy {
  $py = Join-Path $InstallRoot "venv\Scripts\python.exe"
  if (-not (Test-Path $py)) { $py = "python" }
  $script = Join-Path $ProjectRoot "scripts\verify_summary_health.py"
  & $py $script $InstallRoot
  if ($LASTEXITCODE -ne 0) {
    throw "Summary health check failed"
  }
}

Stop-DesklineProcesses
Sync-Install
Start-Deskline
if (-not (Wait-Port -Seconds 25)) {
  throw "Deskline did not open port $Port"
}
Write-Host "Port $Port is up."
Assert-SummaryHealthy

$running = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine -match '-m\s+deskline' })
Write-Host "Running deskline processes: $($running.Count)"
foreach ($p in $running) {
  Write-Host ("  PID {0} {1}" -f $p.ProcessId, $p.Name)
}

$listen = netstat -ano | Select-String "127.0.0.1:8787\s+.*LISTENING"
$listenPids = @($listen | ForEach-Object { ($_ -split '\s+')[-1] } | Select-Object -Unique)
Write-Host ("Listeners on 8787: {0}" -f ($listenPids -join ','))
if ($listenPids.Count -ne 1) {
  throw "Expected exactly one listener on 8787"
}

$url = "http://127.0.0.1:$Port"
Write-Host "Done. Open $url and press Ctrl+F5."
Start-Process $url
