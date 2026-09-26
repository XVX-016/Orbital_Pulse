#Requires -Version 5.1
<#
.SYNOPSIS
    SatQuery AI - one-command startup (Windows / PowerShell).

.DESCRIPTION
    Brings up the full stack unattended:
      1. PostGIS + satquery-service via docker compose
      2. GeoChat-7B inference (see "Execution modes")
      3. Polls GET /health until geochat_loaded:true, failing loudly on timeout
      4. Prints a single "System Ready" banner

    Execution modes
    ---------------
    GeoChat has no standalone inference server - geochat_engine.py loads the
    model *in-process* inside whatever runs main:app. Two consequences:

      host   - satquery-service runs on the host inside ml\geochat\venv, so it
               can see the NVIDIA GPU and /health reports geochat_loaded:true.
               PostGIS still runs in Docker. Chosen automatically when the venv
               exists AND torch reports CUDA available.

      docker - satquery-service runs in its container. ml\ is outside the
               image's build context, so the geochat package is absent and
               /health always reports degraded. Everything except VQA/grounding
               works: STAC ingestion, deterministic metrics, PostGIS history
               and alerting.

.PARAMETER Mode
    Force 'host' or 'docker' instead of auto-detecting.

.PARAMETER SkipGeoChatGate
    Treat a degraded (geochat_loaded:false) service as success. Use on machines
    with no NVIDIA GPU.

.PARAMETER TimeoutSeconds
    How long to wait for geochat_loaded:true. Default 90.

.EXAMPLE
    .\start.ps1
.EXAMPLE
    .\start.ps1 -SkipGeoChatGate
#>
[CmdletBinding()]
param(
    [ValidateSet('host', 'docker')] [string] $Mode,
    [switch] $SkipGeoChatGate,
    [int]    $TimeoutSeconds = 90
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RepoRoot      = Split-Path -Parent $MyInvocation.MyCommand.Definition
$HealthUrl     = if ($env:HEALTH_URL) { $env:HEALTH_URL } else { 'http://localhost:8082/health' }
$LogDir        = Join-Path $RepoRoot 'logs'
$InferenceLog  = Join-Path $LogDir 'geochat-inference.log'
$InferenceErr  = Join-Path $LogDir 'geochat-inference.err.log'
$PidFile       = Join-Path $LogDir 'geochat-inference.pid'

Set-Location $RepoRoot

function Write-Log  { param([string]$m) Write-Host "[start] $m" -ForegroundColor Blue }
function Write-Warn { param([string]$m) Write-Host "[warn]  $m" -ForegroundColor Yellow }
function Stop-WithError {
    param([string]$m)
    Write-Host ''
    Write-Host '+==============================================================+' -ForegroundColor Red
    Write-Host '|  STARTUP FAILED                                              |' -ForegroundColor Red
    Write-Host '+==============================================================+' -ForegroundColor Red
    Write-Host $m -ForegroundColor Red
    exit 1
}

# --- 1. Preflight ------------------------------------------------------------
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Stop-WithError 'docker not found on PATH. Install Docker Desktop first.'
}
& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Stop-WithError 'The Docker daemon is not responding. Start Docker Desktop and retry.'
}
& docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    Stop-WithError "The 'docker compose' plugin is unavailable. Install docker-compose v2+."
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# --- 2. Decide execution mode ------------------------------------------------
$VenvPy = Join-Path $RepoRoot 'ml\geochat\venv\Scripts\python.exe'
if (-not (Test-Path $VenvPy)) { $VenvPy = Join-Path $RepoRoot 'ml/geochat/venv/bin/python' }

function Get-Mode {
    if ($Mode)          { return $Mode }
    if ($env:SATQUERY_MODE) { return $env:SATQUERY_MODE }
    if (Test-Path $VenvPy) {
        & $VenvPy -c 'import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)' *> $null
        if ($LASTEXITCODE -eq 0) { return 'host' }
    }
    return 'docker'
}
$ResolvedMode = Get-Mode
Write-Log "Execution mode: $ResolvedMode"

# --- 3. Bring up containers --------------------------------------------------
if ($ResolvedMode -eq 'host') {
    Write-Log 'Starting PostGIS (satquery-service will run on the host for GPU access)...'
    & docker compose up -d postgis
} else {
    Write-Log 'Starting PostGIS + satquery-service...'
    & docker compose up -d postgis satquery-service
}
if ($LASTEXITCODE -ne 0) { Stop-WithError 'docker compose up failed. Inspect: docker compose logs' }

Write-Log 'Waiting for PostGIS to report healthy...'
$pgId = (& docker compose ps -q postgis).Trim()
if (-not $pgId) { Stop-WithError 'PostGIS container failed to start. Inspect: docker compose logs postgis' }

$pgState = ''
foreach ($i in 1..60) {
    $pgState = (& docker inspect -f '{{.State.Health.Status}}' $pgId 2>$null)
    if ($pgState -eq 'healthy') { break }
    Start-Sleep -Seconds 2
}
if ($pgState -ne 'healthy') {
    Stop-WithError 'PostGIS did not become healthy within 120s. Inspect: docker compose logs postgis'
}
Write-Log 'PostGIS healthy.'

# --- 4. Launch host-side GeoChat inference -----------------------------------
if ($ResolvedMode -eq 'host') {
    # Reap a previous run so re-running never double-binds :8082
    if (Test-Path $PidFile) {
        $oldPid = Get-Content $PidFile -ErrorAction SilentlyContinue
        if ($oldPid) {
            $proc = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Log "Stopping previous inference process (PID $oldPid)..."
                Stop-Process -Id $oldPid -Force -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 2
            }
        }
    }
    if (-not (Test-Path $VenvPy)) {
        Stop-WithError 'Mode=host but no GeoChat venv at ml\geochat\venv. See ml\geochat\SETUP.md.'
    }

    Write-Log "Launching GeoChat inference in the background (log: $InferenceLog)..."
    if (-not $env:SATQUERY_DATABASE_URL) {
        $env:SATQUERY_DATABASE_URL = 'postgresql://orbital_user:orbital_password@localhost:5432/orbital_db'
    }
    $proc = Start-Process -FilePath $VenvPy `
        -ArgumentList '-m', 'uvicorn', 'main:app', '--host', '0.0.0.0', '--port', '8082' `
        -WorkingDirectory (Join-Path $RepoRoot 'satquery-service') `
        -RedirectStandardOutput $InferenceLog `
        -RedirectStandardError  $InferenceErr `
        -NoNewWindow -PassThru
    $proc.Id | Out-File -FilePath $PidFile -Encoding ascii
    Write-Log "Inference PID $($proc.Id)."
}

# --- 5. Health gate ----------------------------------------------------------
Write-Log "Polling $HealthUrl (timeout ${TimeoutSeconds}s)..."

$deadline  = (Get-Date).AddSeconds($TimeoutSeconds)
$health    = $null
$reachable = $false
while ((Get-Date) -lt $deadline) {
    try {
        $health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 5 -ErrorAction Stop
        $reachable = $true
        if ($health.geochat_loaded -eq $true) { break }
        if ($SkipGeoChatGate) { break }
    } catch {
        # Service not up yet - keep polling until the deadline.
    }
    Start-Sleep -Seconds 3
}

if (-not $reachable) {
    if ($ResolvedMode -eq 'host') {
        Write-Warn "Last 20 lines of ${InferenceLog}:"
        Get-Content $InferenceLog -Tail 20 -ErrorAction SilentlyContinue
        Get-Content $InferenceErr -Tail 20 -ErrorAction SilentlyContinue
    } else {
        Write-Warn 'Last 20 lines of satquery-service:'
        & docker compose logs --tail 20 satquery-service
    }
    Stop-WithError "The service never answered $HealthUrl within ${TimeoutSeconds}s."
}

if ($health.geochat_loaded -ne $true) {
    $geochatError = if ($health.PSObject.Properties.Name -contains 'geochat_error' -and $health.geochat_error) {
        $health.geochat_error
    } else { 'unknown' }

    if ($SkipGeoChatGate) {
        Write-Warn 'GeoChat NOT loaded - continuing because -SkipGeoChatGate was passed.'
        Write-Warn "  Reason: $geochatError"
        Write-Warn '  VQA and grounding are unavailable. STAC ingestion, deterministic'
        Write-Warn '  metrics, PostGIS history and alerting all work normally.'
    } else {
        Write-Host ''
        Write-Warn "Service is UP but reports geochat_loaded=false after ${TimeoutSeconds}s."
        Write-Warn "  geochat_error: $geochatError"
        if ($ResolvedMode -eq 'docker') {
            Write-Warn '  Cause: in docker mode the geochat package is not in the image'
            Write-Warn '  (ml\ sits outside the build context), so it can never load.'
            Write-Warn '  Fix: set up ml\geochat\venv per ml\geochat\SETUP.md and re-run,'
            Write-Warn '  or re-run with -SkipGeoChatGate to accept degraded mode.'
        } else {
            Write-Warn "  Inspect: Get-Content $InferenceLog -Tail 50"
        }
        Stop-WithError "GeoChat failed to load within ${TimeoutSeconds}s (see above)."
    }
}

# --- 6. Ready banner ---------------------------------------------------------
Write-Host ''
Write-Host '+==============================================================+' -ForegroundColor Green
Write-Host '|                       SYSTEM READY                           |' -ForegroundColor Green
Write-Host '+==============================================================+' -ForegroundColor Green
'{0,-22} {1}' -f 'Frontend (dev)',    'http://localhost:8080'   | Write-Host
'{0,-22} {1}' -f 'Frontend (docker)', 'http://localhost:5173'   | Write-Host
'{0,-22} {1}' -f 'API',               'http://localhost:8082'   | Write-Host
'{0,-22} {1}' -f 'Health',            $HealthUrl                | Write-Host
'{0,-22} {1}' -f 'Alerts',            'http://localhost:8082/api/alerts' | Write-Host
'{0,-22} {1}' -f 'PostGIS',           'postgresql://orbital_user:***@localhost:5432/orbital_db' | Write-Host
Write-Host ''
'{0,-22} {1}' -f 'Mode',           $ResolvedMode          | Write-Host
'{0,-22} {1}' -f 'Service status', $health.status         | Write-Host
'{0,-22} {1}' -f 'GeoChat loaded', $health.geochat_loaded | Write-Host
if ($health.PSObject.Properties.Name -contains 'peak_vram_gb' -and $health.peak_vram_gb -gt 0) {
    '{0,-22} {1} GB' -f 'Peak VRAM', $health.peak_vram_gb | Write-Host
}
if ($ResolvedMode -eq 'host') {
    '{0,-22} {1}' -f 'Inference log', $InferenceLog | Write-Host
}
Write-Host ''
