<#
.SYNOPSIS
    TalentLens - Development Startup Script (Windows PowerShell)

.DESCRIPTION
    Starts infrastructure (MongoDB, Redis, Redpanda, Qdrant, Elasticsearch)
    via Docker Compose, then launches every Python micro-service in a
    separate PowerShell window so you can watch their logs individually.

.USAGE
    .\scripts\start_dev.ps1                  # Start everything
    .\scripts\start_dev.ps1 -InfraOnly       # Only spin up Docker infra
    .\scripts\start_dev.ps1 -ServicesOnly    # Skip Docker, just start services
    .\scripts\start_dev.ps1 -Stop            # docker compose down

.NOTES
    Prerequisites:
      - Docker Desktop running
      - Python 3.12 installed and on PATH
      - pip install -r shared/requirements.txt (run once before first start)
#>

[CmdletBinding()]
param(
    [switch]$InfraOnly,
    [switch]$ServicesOnly,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

# ---- Helper functions --------------------------------------------------------
function Write-Banner  { param($msg) Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok      { param($msg) Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn    { param($msg) Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Write-Fail    { param($msg) Write-Host "  [X]  $msg" -ForegroundColor Red }

# ---- Pre-flight checks -------------------------------------------------------
Write-Host "  Checking Docker Desktop..." -ForegroundColor DarkGray
try {
    $null = docker version 2>&1
} catch {
    Write-Fail "Docker Desktop is not running or not reachable"
    Write-Host "    Start Docker Desktop first and wait for the green status, then re-run this script." -ForegroundColor Yellow
    exit 1
}
Write-Ok "Docker Desktop is running"

# ---- Stop --------------------------------------------------------------------
if ($Stop) {
    Write-Banner "Stopping all containers"
    docker compose down --remove-orphans
    Write-Ok "All containers stopped"
    exit 0
}

# ---- Infrastructure ----------------------------------------------------------
$INFRA_SERVICES = @(
    "mongodb","redis","redpanda","qdrant","elasticsearch",
    "minio","redpanda-console","kafka-init","minio-init",
    "prometheus","grafana"
)

if (-not $ServicesOnly) {
    Write-Banner "Starting infrastructure services"

    Write-Host "  Pulling images (first run may take a few minutes)..." -ForegroundColor DarkGray
    & cmd /c "docker compose pull $($INFRA_SERVICES -join ' ') --quiet 2>&1" | Out-Host
    if ($LASTEXITCODE -ne 0) { Write-Fail "docker compose pull failed (see output above)"; exit 1 }

    Write-Host "  Starting containers..." -ForegroundColor DarkGray
    & cmd /c "docker compose up -d $($INFRA_SERVICES -join ' ') 2>&1" | Out-Host
    if ($LASTEXITCODE -ne 0) { Write-Fail "docker compose up failed (see output above)"; exit 1 }

    # Quick check: any containers exited immediately after start?
    $exited = docker compose ps --format json 2>$null |
        ForEach-Object { $_ | ConvertFrom-Json -ErrorAction SilentlyContinue } |
        Where-Object { $INFRA_SERVICES -contains $_.Service -and $_.State -eq "exited" }
    if ($exited) {
        Write-Warn "The following containers exited on start:"
        foreach ($c in $exited) { Write-Host "     - $($c.Name): exit $($_.ExitCode)" -ForegroundColor Yellow }
        Write-Host "    Run 'docker logs <name>' to see why." -ForegroundColor Yellow
    }

    Write-Host "  Waiting for services to become healthy..." -ForegroundColor DarkGray
    $timeout = 90
    $elapsed = 0
    while ($elapsed -lt $timeout) {
        $unhealthy = docker compose ps --format json 2>$null |
            ForEach-Object { $_ | ConvertFrom-Json -ErrorAction SilentlyContinue } |
            Where-Object { $_ -and ($_.Health -eq "unhealthy" -or ($_.Health -eq "starting" -and $_.Name -ne "jip-kafka-init")) }
        if (-not $unhealthy) { break }
        Start-Sleep -Seconds 5
        $elapsed += 5
        Write-Host "    [$elapsed s] Still waiting..." -ForegroundColor DarkGray
    }

    Write-Ok "Infrastructure ready"

    Write-Host ""
    Write-Host "  Infrastructure endpoints:" -ForegroundColor White
    Write-Host "    MongoDB          : mongodb://localhost:27017" -ForegroundColor Gray
    Write-Host "    Redis            : redis://localhost:6379"    -ForegroundColor Gray
    Write-Host "    Redpanda Console : http://localhost:8080"     -ForegroundColor Gray
    Write-Host "    Qdrant           : http://localhost:6333"     -ForegroundColor Gray
    Write-Host "    Elasticsearch    : http://localhost:9200"     -ForegroundColor Gray
    Write-Host "    MinIO Console    : http://localhost:9001"     -ForegroundColor Gray
}

if ($InfraOnly) {
    Write-Ok "InfraOnly mode - skipping Python services"
    exit 0
}

# ---- Python services ---------------------------------------------------------
Write-Banner "Starting Python micro-services (each in a new window)"

$PYTHONPATH = (Get-Location).Path
$env:PYTHONPATH = $PYTHONPATH
$env:APP_ENV    = "development"

# Load .env into current session
if (Test-Path ".env") {
    Get-Content ".env" | Where-Object { $_ -match "^\s*[^#]" -and $_ -match "=" } | ForEach-Object {
        $parts = $_ -split "=", 2
        $key   = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
    Write-Ok ".env loaded"
}

# Service definitions
# NOTE: Services with HTTP APIs (FastAPI `app = FastAPI(...)`) use `uvicorn ...:app`.
#       Kafka BACKGROUND WORKERS (only `async def main()` exists, no HTTP endpoints)
#       use `python -m services.X.main`. Analytics is a WORKER, not an API.
$SERVICES = @(
    @{ Name = "Gateway";      Cmd = "uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000 --reload" },
    @{ Name = "Collector";    Cmd = "python -m services.collector.main" },
    @{ Name = "Cleaner";      Cmd = "python -m services.cleaner.main" },
    @{ Name = "Deduplicator"; Cmd = "python -m services.deduplicator.main" },
    @{ Name = "Enrichment";   Cmd = "python -m services.enrichment.main" },
    @{ Name = "Verifier";     Cmd = "python -m services.verifier.main" },
    @{ Name = "Embedder";     Cmd = "python -m services.embedder.main" },
    @{ Name = "Notifier";     Cmd = "python -m services.notifier.main" },
    @{ Name = "Search";       Cmd = "uvicorn services.search.main:app --host 0.0.0.0 --port 8002 --reload" },
    @{ Name = "Analytics";    Cmd = "python -m services.analytics.main" }
)

foreach ($svc in $SERVICES) {
    $title   = "TalentLens :: $($svc.Name)"
    $svcCmd  = $svc.Cmd

    # Build the inner command string with safe escaping (no Unicode arrows)
    $inner = "`$Host.UI.RawUI.WindowTitle = '$title'; " +
             "`$env:PYTHONPATH = '$PYTHONPATH'; " +
             "`$env:APP_ENV = 'development'; " +
             "$svcCmd"

    Start-Process powershell -ArgumentList "-NoExit", "-Command", $inner
    Write-Ok "$($svc.Name) -> $svcCmd"
    Start-Sleep -Milliseconds 300
}

Write-Host ""
Write-Banner "All services started"
Write-Host "  Service endpoints:" -ForegroundColor White
Write-Host "    Gateway API   : http://localhost:8000/docs" -ForegroundColor Gray
Write-Host "    Search API    : http://localhost:8002/docs" -ForegroundColor Gray
Write-Host "    Analytics API : http://localhost:8003/docs" -ForegroundColor Gray
Write-Host "    Job Board     : http://localhost:3000"      -ForegroundColor Gray
Write-Host "    Admin UI      : http://localhost:3001"      -ForegroundColor Gray
Write-Host ""
Write-Host "  Run health check : python scripts/health_check.py"  -ForegroundColor DarkGray
Write-Host "  Seed sample data : python scripts/seed_data.py"     -ForegroundColor DarkGray
Write-Host "  Stop infra       : .\scripts\start_dev.ps1 -Stop"   -ForegroundColor DarkGray
Write-Host ""
