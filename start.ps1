#Requires -Version 5.1
<#
.SYNOPSIS
    SphereVoice — Windows Start Script
    Starts PostgreSQL, Redis, Backend (port 2998), Frontend (port 2999).
    Kills any conflicting processes on those ports before starting.

.PARAMETER HotReload
    Run backend and frontend with file watching enabled (default).

.PARAMETER NoHotReload
    Run backend and frontend without file watching.

.EXAMPLE
    .\start.ps1
    .\start.ps1 -HotReload
    .\start.ps1 -NoHotReload
#>
[CmdletBinding()]
param(
    [switch]$HotReload,
    [switch]$NoHotReload,
    [switch]$Help
)

$ErrorActionPreference = "Continue"

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────
$RootDir = $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$BackendPort = 2998
$FrontendPort = 2999

if ($NoHotReload) {
    $EnableHotReload = $false
}
else {
    $EnableHotReload = $true
}

# ─────────────────────────────────────────────────────────────
# Logging helpers
# ─────────────────────────────────────────────────────────────
function Log { param([string]$Msg) Write-Host "[VOX] $Msg" -ForegroundColor Green }
function Warn { param([string]$Msg) Write-Host "[VOX] $Msg" -ForegroundColor Yellow }
function Err { param([string]$Msg) Write-Host "[VOX] $Msg" -ForegroundColor Red }

if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Detailed
    exit 0
}

# ─────────────────────────────────────────────────────────────
# Ensure git hooks are configured
# ─────────────────────────────────────────────────────────────
if (Test-Path (Join-Path $RootDir ".githooks")) {
    try {
        git -C $RootDir config core.hooksPath .githooks 2>$null
        Log "Git hooks path set to .githooks/"
    }
    catch { }
}

# ─────────────────────────────────────────────────────────────
# Port management (Windows-native)
# ─────────────────────────────────────────────────────────────
function Clear-Port {
    param([int]$Port)

    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($connections) {
        $procIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        Warn "Port $Port is in use (PIDs: $($procIds -join ', ')) - killing..."
        foreach ($procId in $procIds) {
            try {
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
            catch { }
        }
        Start-Sleep -Seconds 1

        $still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($still) {
            Err "Failed to free port $Port. Aborting."
            exit 1
        }
        Log "Port $Port freed."
    }
    else {
        Log "Port $Port is available."
    }
}

# ─────────────────────────────────────────────────────────────
# Cleanup on exit
# ─────────────────────────────────────────────────────────────
$script:BackendProcess = $null
$script:FrontendProcess = $null

function Cleanup {
    Log "Shutting down..."
    foreach ($proc in @($script:BackendProcess, $script:FrontendProcess)) {
        if ($proc -and -not $proc.HasExited) {
            try {
                # Kill the process tree
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                # Also kill any child processes
                Get-CimInstance Win32_Process -Filter "ParentProcessId=$($proc.Id)" -ErrorAction SilentlyContinue |
                ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
            }
            catch { }
        }
    }
    Log "All services stopped."
}

# Register cleanup for Ctrl+C
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Cleanup } -ErrorAction SilentlyContinue
trap { Cleanup; break }

# ─────────────────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────────────────
Log "==================================================="
Log "  SphereVoice - Starting all services (Windows)"
Log "  Backend:  http://localhost:$BackendPort"
Log "  Frontend: http://localhost:$FrontendPort"
if ($EnableHotReload) {
    Log "  Mode:     hot reload enabled"
}
else {
    Log "  Mode:     hot reload disabled"
}
Log "==================================================="
Write-Host ""

Clear-Port $BackendPort
Clear-Port $FrontendPort

# ─────────────────────────────────────────────────────────────
# 1. Start Docker services (PostgreSQL + Redis)
# ─────────────────────────────────────────────────────────────
Log "Starting Docker services (PostgreSQL + Redis)..."
Push-Location $RootDir
try {
    docker compose up -d postgres redis --wait 2>&1 | ForEach-Object { Write-Host "  $_" }
}
finally {
    Pop-Location
}
# ─────────────────────────────────────────────────────────────
# 2. Backend setup
# ─────────────────────────────────────────────────────────────
Log "Setting up backend..."

$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$VenvPip = Join-Path $BackendDir ".venv\Scripts\pip.exe"

if (-not (Test-Path $VenvPython)) {
    Warn "Creating Python virtual environment..."
    & python -m venv (Join-Path $BackendDir ".venv")
    if ($LASTEXITCODE -ne 0) {
        Err "Failed to create virtual environment."
        exit 1
    }
}

# Install/update deps
Log "Checking backend dependencies..."
& $VenvPip install -q "setuptools<71" 2>$null
& $VenvPip install -q -r (Join-Path $BackendDir "requirements.txt") 2>&1 | Select-Object -Last 3
if ($LASTEXITCODE -ne 0) {
    Warn "Pip reported conflicts - checking if core deps are present..."
    & $VenvPython -c "import fastapi, sqlalchemy, alembic" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Err "Critical dependencies missing. Fix requirements.txt conflicts."
        exit 1
    }
    Log "Core dependencies already installed - continuing."
}
else {
    Log "Dependencies up to date."
}

# Run migrations
Log "Running database migrations..."
Push-Location $BackendDir
try {
    & $VenvPython -m alembic upgrade head 2>&1 | Select-String -Pattern "Running upgrade|Context impl"
}
finally {
    Pop-Location
}

# Grant permissions (requires psql on PATH or Docker exec)
try {
    $env:PGPASSWORD = "postgres"
    $grantSql = "GRANT ALL ON ALL TABLES IN SCHEMA public TO vox_app; GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO vox_app;"
    & psql -h localhost -p 5434 -U postgres -d vox_dev -c $grantSql 2>$null
}
catch { }
finally { $env:PGPASSWORD = $null }

# Seed data if empty
try {
    $env:PGPASSWORD = "postgres"
    $tenantCount = & psql -h localhost -p 5434 -U postgres -d vox_dev -tAc "SELECT count(*) FROM tenants" 2>$null
    $env:PGPASSWORD = $null
    $tenantCount = ($tenantCount -replace '\s', '')
    if (-not $tenantCount) { $tenantCount = "0" }
}
catch {
    $tenantCount = "0"
    $env:PGPASSWORD = $null
}

if ($tenantCount -eq "0") {
    Log "Seeding initial data..."
    Push-Location $BackendDir
    try {
        & $VenvPython seed.py 2>&1 | Select-Object -Last 5
    }
    finally {
        Pop-Location
    }
}
else {
    Log "Database already has $tenantCount tenant(s) - skipping seed."
}

Log "Backend setup complete."
Write-Host ""

# ─────────────────────────────────────────────────────────────
# 3. Frontend setup
# ─────────────────────────────────────────────────────────────
Log "Setting up frontend..."

$pnpmCmd = Get-Command pnpm -ErrorAction SilentlyContinue
if (-not $pnpmCmd) {
    Warn "pnpm not found, installing via corepack..."
    corepack enable
    corepack prepare pnpm@latest --activate
}

Push-Location $FrontendDir
try {
    Log "Installing frontend dependencies..."
    pnpm install --frozen-lockfile 2>&1 | Select-Object -Last 3
}
finally {
    Pop-Location
}

Log "Frontend setup complete."
Write-Host ""

# ─────────────────────────────────────────────────────────────
# 4. Start Backend (port 2998)
# ─────────────────────────────────────────────────────────────
Log "Starting backend on port $BackendPort..."

$backendArgs = @("-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "$BackendPort", "--log-level", "info")
if ($EnableHotReload) {
    $backendArgs += "--reload"
}

$script:BackendProcess = Start-Process -FilePath $VenvPython -ArgumentList $backendArgs `
    -WorkingDirectory $BackendDir -PassThru -NoNewWindow

# Wait for backend to be ready
Log "Waiting for backend to be ready..."
for ($i = 1; $i -le 30; $i++) {
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:$BackendPort/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        $ready = $true
        break
    }
    catch { }
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:$BackendPort/api/v1/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        $ready = $true
        break
    }
    catch { }
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:$BackendPort/docs" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        $ready = $true
        break
    }
    catch { }
    Start-Sleep -Seconds 1
}

if ($script:BackendProcess.HasExited) {
    Err "Backend failed to start! Check logs above."
    exit 1
}
Log "Backend running (PID $($script:BackendProcess.Id)) on http://localhost:$BackendPort"
Write-Host ""

# ─────────────────────────────────────────────────────────────
# 5. Start Frontend (port 2999)
# ─────────────────────────────────────────────────────────────
Log "Starting frontend on port $FrontendPort..."
$env:PORT = "$FrontendPort"

if ($EnableHotReload) {
    $frontendCmd = "dev"
}
else {
    Log "Building frontend for non-watch mode..."
    Push-Location $FrontendDir
    try { pnpm run build } finally { Pop-Location }
    $frontendCmd = "start"
}

$script:FrontendProcess = Start-Process -FilePath "pnpm" -ArgumentList @("run", $frontendCmd) `
    -WorkingDirectory $FrontendDir -PassThru -NoNewWindow

# Wait for frontend to be ready
Log "Waiting for frontend to be ready..."
for ($i = 1; $i -le 45; $i++) {
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:$FrontendPort" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        break
    }
    catch { }
    Start-Sleep -Seconds 1
}

if ($script:FrontendProcess.HasExited) {
    Err "Frontend failed to start! Check logs above."
    exit 1
}
Log "Frontend running (PID $($script:FrontendProcess.Id)) on http://localhost:$FrontendPort"

Write-Host ""
Log "==================================================="
Log "  SphereVoice is fully running!"
Log ""
Log "  Backend API:  http://localhost:$BackendPort"
Log "  SphereVoice Platform is fully running!"
Log "  Frontend:     http://localhost:$FrontendPort"
if ($EnableHotReload) {
    Log "  Reload Mode:  watching backend and frontend files"
}
else {
    Log "  Reload Mode:  disabled"
}
Log "  PostgreSQL:   localhost:5434"
Log "  Redis:        localhost:6382"
Log ""
if ($EnableHotReload) {
    Log "  Edit files and the app will reload automatically."
}
Log "  Press Ctrl+C to stop all services."
Log "==================================================="

# Keep script alive — wait for both processes
try {
    while ($true) {
        if ($script:BackendProcess.HasExited -and $script:FrontendProcess.HasExited) {
            Log "Both services have exited."
            break
        }
        if ($script:BackendProcess.HasExited) {
            Warn "Backend process exited unexpectedly (exit code $($script:BackendProcess.ExitCode))."
            break
        }
        if ($script:FrontendProcess.HasExited) {
            Warn "Frontend process exited unexpectedly (exit code $($script:FrontendProcess.ExitCode))."
            break
        }
        Start-Sleep -Seconds 2
    }
}
finally {
    Cleanup
}
} finally {
    Cleanup
}
