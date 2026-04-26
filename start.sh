#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────
# SphereVoice Platform — Start Script
# Starts PostgreSQL, Redis, Backend (port 2998), Frontend (port 2999)
# Kills any conflicting processes on those ports before starting.
#
# Windows users: run start.ps1 instead (PowerShell).
# ─────────────────────────────────────────────────────────────

# ── Detect Windows (MSYS/Git Bash/Cygwin) and redirect ─────
case "$(uname -s 2>/dev/null || echo Unknown)" in
    MINGW*|MSYS*|CYGWIN*)
        echo ""
        echo "[SphereVoice] Detected Windows environment ($(uname -s))."
        echo "[SphereVoice] This bash script is designed for macOS/Linux."
        echo "[SphereVoice] Please use the PowerShell script instead:"
        echo ""
        echo "    .\\start.ps1"
        echo ""
        exit 1
        ;;
esac

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

BACKEND_PORT=2998
FRONTEND_PORT=2999
HOT_RELOAD=1

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log()  { echo -e "${GREEN}[SphereVoice]${NC} $*"; }
warn() { echo -e "${YELLOW}[SphereVoice]${NC} $*"; }
err()  { echo -e "${RED}[SphereVoice]${NC} $*"; }

usage() {
    cat <<'EOF'
Usage: ./start.sh [options]

Options:
  --hot-reload, --watch   Run backend and frontend with file watching enabled.
  --no-hot-reload         Run backend and frontend without file watching.
  -h, --help              Show this help message.

Examples:
  ./start.sh
  ./start.sh --hot-reload
  ./start.sh --no-hot-reload
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --hot-reload|--watch)
            HOT_RELOAD=1
            ;;
        --no-hot-reload)
            HOT_RELOAD=0
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            err "Unknown option: $1"
            echo ""
            usage
            exit 1
            ;;
    esac
    shift
done

# ── Ensure git hooks are configured ────────────────────────
if [ -d "$ROOT_DIR/.githooks" ]; then
    git -C "$ROOT_DIR" config core.hooksPath .githooks 2>/dev/null && \
        log "Git hooks path set to .githooks/"
fi

# ── Cleanup on exit ─────────────────────────────────────────
cleanup() {
    log "Shutting down..."
    # Kill process trees (uvicorn --reload and pnpm spawn children)
    for pid in "${BACKEND_PID:-}" "${FRONTEND_PID:-}"; do
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            # Kill the entire process group
            kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    done
    log "All services stopped."
}
trap cleanup EXIT INT TERM

# ── 1. Kill conflicting ports (macOS-compatible) ────────────
free_port() {
    local port=$1
    local pids
    pids=$(lsof -ti :"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        warn "Port $port is in use (PIDs: $(echo $pids | tr '\n' ' '))— killing..."
        echo "$pids" | xargs kill -9 2>/dev/null || true
        sleep 1
        if lsof -ti :"$port" -sTCP:LISTEN >/dev/null 2>&1; then
            err "Failed to free port $port. Aborting."
            exit 1
        fi
        log "Port $port freed."
    else
        log "Port $port is available."
    fi
}

log "═══════════════════════════════════════════════════"
log "  SphereVoice Platform — Starting all services"
log "  Backend:  http://localhost:$BACKEND_PORT"
log "  Frontend: http://localhost:$FRONTEND_PORT"
if [[ "$HOT_RELOAD" -eq 1 ]]; then
    log "  Mode:     hot reload enabled"
else
    log "  Mode:     hot reload disabled"
fi
log "═══════════════════════════════════════════════════"
echo ""

free_port $BACKEND_PORT
free_port $FRONTEND_PORT

# ── 2. Start Docker services (PostgreSQL + Redis) ──────────
log "Starting Docker services (PostgreSQL + Redis)..."
cd "$ROOT_DIR"
docker compose up -d postgres redis --wait 2>&1 | while read -r line; do echo "  $line"; done

# Verify services are healthy
if ! docker compose ps --format '{{.Service}} {{.Status}}' 2>/dev/null | grep -q "healthy"; then
    # Fallback check
    docker compose ps 2>&1 | tail -5
fi
log "Docker services ready."
echo ""

# ── 3. Backend setup ────────────────────────────────────────
log "Setting up backend..."

# Ensure venv exists
if [[ ! -f "$BACKEND_DIR/.venv/bin/python" ]]; then
    warn "Creating Python virtual environment..."
    python3 -m venv "$BACKEND_DIR/.venv"
fi

PYTHON="$BACKEND_DIR/.venv/bin/python"
PIP="$BACKEND_DIR/.venv/bin/pip"

# Install/update deps (tolerate conflicts if already installed)
log "Checking backend dependencies..."
# Ensure setuptools with pkg_resources (needed by OpenTelemetry instrumentation)
"$PIP" install -q "setuptools<71" 2>/dev/null || true
if "$PIP" install -q -r "$BACKEND_DIR/requirements.txt" 2>&1 | tail -3; then
    log "Dependencies up to date."
else
    warn "Pip reported conflicts — checking if core deps are present..."
    if "$PYTHON" -c "import fastapi, sqlalchemy, alembic" 2>/dev/null; then
        log "Core dependencies already installed — continuing."
    else
        err "Critical dependencies missing. Fix requirements.txt conflicts."
        exit 1
    fi
fi

# Run migrations
log "Running database migrations..."
cd "$BACKEND_DIR"
"$PYTHON" -m alembic upgrade head 2>&1 | grep -E "Running upgrade|Context impl" || true

# Ensure SphereVoice_app role has grants on all tables (needed after new migrations)
PGPASSWORD=postgres psql -h localhost -p 5434 -U postgres -d SphereVoice_dev -c "GRANT ALL ON ALL TABLES IN SCHEMA public TO SphereVoice_app; GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO SphereVoice_app;" 2>/dev/null || true

# Seed data if empty
TENANT_COUNT=$( PGPASSWORD=postgres psql -h localhost -p 5434 -U postgres -d SphereVoice_dev -tAc "SELECT count(*) FROM tenants" 2>/dev/null || echo "0" )
if [[ "$TENANT_COUNT" -eq 0 ]]; then
    log "Seeding initial data..."
    "$PYTHON" seed.py 2>&1 | tail -5
else
    log "Database already has $TENANT_COUNT tenant(s) — skipping seed."
fi

log "Backend setup complete."
echo ""

# ── 4. Frontend setup ───────────────────────────────────────
log "Setting up frontend..."

if ! command -v pnpm &>/dev/null; then
    warn "pnpm not found, installing via corepack..."
    corepack enable && corepack prepare pnpm@latest --activate
fi

cd "$FRONTEND_DIR"
log "Installing frontend dependencies..."
pnpm install --frozen-lockfile 2>&1 | tail -3

log "Frontend setup complete."
echo ""

# ── 5. Start Backend (port 2998) ────────────────────────────
log "Starting backend on port $BACKEND_PORT..."
cd "$BACKEND_DIR"
BACKEND_CMD=(
    "$PYTHON" -m uvicorn app.main:app
    --host 0.0.0.0
    --port "$BACKEND_PORT"
    --log-level info
)

if [[ "$HOT_RELOAD" -eq 1 ]]; then
    BACKEND_CMD+=(--reload)
fi

"${BACKEND_CMD[@]}" &
BACKEND_PID=$!

# Wait for backend to be ready
log "Waiting for backend to be ready..."
for i in $(seq 1 30); do
    if curl -sf "http://localhost:$BACKEND_PORT/health" >/dev/null 2>&1 || \
       curl -sf "http://localhost:$BACKEND_PORT/api/v1/health" >/dev/null 2>&1 || \
       curl -sf "http://localhost:$BACKEND_PORT/docs" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

if kill -0 "$BACKEND_PID" 2>/dev/null; then
    log "Backend running (PID $BACKEND_PID) on http://localhost:$BACKEND_PORT"
else
    err "Backend failed to start! Check logs above."
    exit 1
fi
echo ""

# ── 6. Start Frontend (port 2999) ───────────────────────────
log "Starting frontend on port $FRONTEND_PORT..."
cd "$FRONTEND_DIR"
if [[ "$HOT_RELOAD" -eq 1 ]]; then
    FRONTEND_CMD=(pnpm run dev)
else
    log "Building frontend for non-watch mode..."
    pnpm run build
    FRONTEND_CMD=(pnpm run start)
fi

PORT=$FRONTEND_PORT "${FRONTEND_CMD[@]}" &
FRONTEND_PID=$!

# Wait for frontend to be ready
log "Waiting for frontend to be ready..."
for i in $(seq 1 45); do
    if curl -sf "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

if kill -0 "$FRONTEND_PID" 2>/dev/null; then
    log "Frontend running (PID $FRONTEND_PID) on http://localhost:$FRONTEND_PORT"
else
    err "Frontend failed to start! Check logs above."
    exit 1
fi

echo ""
log "═══════════════════════════════════════════════════"
log "  ✅ SphereVoice Platform is fully running!"
log ""
log "  🔧 Backend API:  ${CYAN}http://localhost:$BACKEND_PORT${NC}"
log "  📖 API Docs:     ${CYAN}http://localhost:$BACKEND_PORT/docs${NC}"
log "  🖥️  Frontend:     ${CYAN}http://localhost:$FRONTEND_PORT${NC}"
if [[ "$HOT_RELOAD" -eq 1 ]]; then
    log "  🔁 Reload Mode:  ${CYAN}watching backend and frontend files${NC}"
else
    log "  🔁 Reload Mode:  ${CYAN}disabled${NC}"
fi
log "  🐘 PostgreSQL:   localhost:5434"
log "  🔴 Redis:        localhost:6382"
log ""
if [[ "$HOT_RELOAD" -eq 1 ]]; then
    log "  Edit files and the app will reload automatically."
fi
log "  Press Ctrl+C to stop all services."
log "═══════════════════════════════════════════════════"

# Keep script alive, wait for both processes
wait
