#!/usr/bin/env bash
set -euo pipefail

# SphereVoice Platform — Production-like Local Start Script
# Starts PostgreSQL, Redis, backend, Celery worker, and frontend in production-ish mode.

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

FRONTEND_MODE="prod"

BACKEND_PORT=2998
FRONTEND_PORT=2999

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[SphereVoice PROD-LIKE]${NC} $*"; }
warn() { echo -e "${YELLOW}[SphereVoice PROD-LIKE]${NC} $*"; }
err()  { echo -e "${RED}[SphereVoice PROD-LIKE]${NC} $*"; }

usage() {
    cat <<'EOF'
Usage: ./start-prod-like.sh [options]

Options:
  --dev        Start the frontend with `pnpm run dev` instead of `pnpm run build` + `pnpm run start`.
  -h, --help   Show this help message.

Examples:
  ./start-prod-like.sh
  ./start-prod-like.sh --dev
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dev)
            FRONTEND_MODE="dev"
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

CLEANUP_DONE=0

cleanup() {
    if [[ "$CLEANUP_DONE" -eq 1 ]]; then
        return
    fi
    CLEANUP_DONE=1
    trap - EXIT INT TERM
    log "Shutting down..."
    for pid in "${BACKEND_PID:-}" "${WORKER_PID:-}" "${BEAT_PID:-}" "${FRONTEND_PID:-}"; do
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    done
    log "Application processes stopped. Docker services remain running."
}
trap cleanup EXIT INT TERM

_get_pids_on_port() {
    local port=$1
    if command -v lsof &>/dev/null; then
        lsof -ti "TCP:$port" -sTCP:LISTEN 2>/dev/null | sort -u || true
    elif command -v ss &>/dev/null; then
        ss -ltnp "( sport = :$port )" 2>/dev/null | grep -o 'pid=[0-9]\+' | cut -d= -f2 | sort -u || true
    else
        true
    fi
}

free_port() {
    local port=$1
    local pids
    pids=$(_get_pids_on_port "$port")
    if [[ -n "$pids" ]]; then
        warn "Port $port is in use (PIDs: $(echo "$pids" | tr '\n' ' ')) — stopping existing process(es)..."
        echo "$pids" | xargs kill -TERM 2>/dev/null || true

        for _ in $(seq 1 5); do
            if [[ -z "$(_get_pids_on_port "$port")" ]]; then
                break
            fi
            sleep 1
        done

        local remaining
        remaining=$(_get_pids_on_port "$port")
        if [[ -n "$remaining" ]]; then
            warn "Port $port still busy after graceful stop — forcing termination."
            echo "$remaining" | xargs kill -9 2>/dev/null || true
            sleep 1
        fi

        if [[ -n "$(_get_pids_on_port "$port")" ]]; then
            err "Failed to free port $port. Aborting."
            exit 1
        fi
        log "Port $port is now available."
    else
        log "Port $port is available."
    fi
}

require_file() {
    local path=$1
    local label=$2
    if [[ ! -f "$path" ]]; then
        err "$label is missing at $path"
        exit 1
    fi
}

log "═══════════════════════════════════════════════════"
log "  SphereVoice Platform — Production-like local startup"
log "  Backend:  http://localhost:$BACKEND_PORT"
log "  Frontend: http://localhost:$FRONTEND_PORT"
if [[ "$FRONTEND_MODE" == "dev" ]]; then
    log "  Frontend mode: Next.js dev server"
else
    log "  Frontend mode: build + next start"
fi
log "═══════════════════════════════════════════════════"
echo ""

require_file "$BACKEND_DIR/.env" "Backend env file"
require_file "$FRONTEND_DIR/.env.local" "Frontend env file"
require_file "$FRONTEND_DIR/package.json" "Frontend package.json"

free_port "$BACKEND_PORT"
free_port "$FRONTEND_PORT"

log "Starting Docker services (PostgreSQL + Redis)..."
cd "$ROOT_DIR"

# Stop any leftover containers from other compose projects that occupy the same ports.
for port in 5434 6382; do
    existing=$(docker ps -q --filter "publish=$port" 2>/dev/null || true)
    if [[ -n "$existing" ]]; then
        warn "Stopping existing container(s) on port $port: $existing"
        docker stop $existing >/dev/null 2>&1 || true
    fi
done

docker compose up -d postgres redis --wait 2>&1 | while read -r line; do echo "  $line"; done
log "Docker services ready."
echo ""

log "Preparing backend..."

# Detect OS to use correct venv paths (Windows: Scripts/, Unix: bin/)
if [[ "$(uname -s)" == MINGW* ]] || [[ "$(uname -s)" == MSYS* ]] || [[ "$(uname -s)" == CYGWIN* ]] || [[ -d "$BACKEND_DIR/.venv/Scripts" && ! -d "$BACKEND_DIR/.venv/bin" ]]; then
    VENV_BIN="Scripts"
    PYTHON_CMD="python"
else
    VENV_BIN="bin"
    PYTHON_CMD="python3"
fi

if [[ ! -f "$BACKEND_DIR/.venv/$VENV_BIN/python" ]] && [[ ! -f "$BACKEND_DIR/.venv/$VENV_BIN/python.exe" ]]; then
    warn "Creating Python virtual environment..."
    $PYTHON_CMD -m venv "$BACKEND_DIR/.venv"
fi

PYTHON="$BACKEND_DIR/.venv/$VENV_BIN/python"
PIP="$BACKEND_DIR/.venv/$VENV_BIN/pip"
CELERY_BIN="$BACKEND_DIR/.venv/$VENV_BIN/celery"

"$PIP" install -q "setuptools<71" 2>/dev/null || true
if "$PIP" install -q -r "$BACKEND_DIR/requirements.txt" 2>&1 | tail -3; then
    log "Backend dependencies ready."
else
    warn "pip reported conflicts — checking core dependencies..."
    if "$PYTHON" -c "import fastapi, sqlalchemy, alembic, celery" 2>/dev/null; then
        log "Core backend dependencies already installed — continuing."
    else
        err "Critical backend dependencies are missing."
        exit 1
    fi
fi

cd "$BACKEND_DIR"
log "Running database migrations..."
"$PYTHON" -m alembic upgrade head 2>&1 | grep -E "Running upgrade|Context impl" || true

PGPASSWORD=postgres psql -h localhost -p 5434 -U postgres -d SphereVoice_dev -c "GRANT ALL ON ALL TABLES IN SCHEMA public TO SphereVoice_app; GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO SphereVoice_app;" 2>/dev/null || true

TENANT_COUNT=$(PGPASSWORD=postgres psql -h localhost -p 5434 -U postgres -d SphereVoice_dev -tAc "SELECT count(*) FROM tenants" 2>/dev/null || echo "0")
if [[ "$TENANT_COUNT" -eq 0 ]]; then
    log "Seeding initial data..."
    "$PYTHON" seed.py 2>&1 | tail -5
else
    log "Database already has $TENANT_COUNT tenant(s) — skipping seed."
fi

log "Preparing frontend..."
cd "$FRONTEND_DIR"
log "Using frontend directory: $FRONTEND_DIR"
if ! command -v pnpm &>/dev/null; then
    warn "pnpm not found, installing via corepack..."
    corepack enable && corepack prepare pnpm@latest --activate
fi

pnpm install --frozen-lockfile 2>&1 | tail -3
if [[ "$FRONTEND_MODE" == "dev" ]]; then
    log "Skipping frontend build because --dev was requested."
else
    log "Building frontend for production-like run..."
    pnpm run build
fi
echo ""

LOG_FILE="/tmp/SphereVoice-backend-$(date +%Y%m%d-%H%M%S).log"
log "Starting backend (no reload)..."
log "Backend logs → ${CYAN}$LOG_FILE${NC}"
cd "$BACKEND_DIR"
ENVIRONMENT=development DEBUG=false OTEL_EXPORTER_OTLP_ENDPOINT= "$PYTHON" -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$BACKEND_PORT" \
    --log-level debug 2>&1 | tee "$LOG_FILE" &
BACKEND_PID=$!

log "Waiting for backend readiness..."
for i in $(seq 1 30); do
    if curl -sf "http://localhost:$BACKEND_PORT/ready" >/dev/null 2>&1 || \
       curl -sf "http://localhost:$BACKEND_PORT/health" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    err "Backend failed to start."
    exit 1
fi

log "Starting Celery worker..."
ENVIRONMENT=development DEBUG=false OTEL_EXPORTER_OTLP_ENDPOINT= "$CELERY_BIN" -A app.workers.celery_app worker --loglevel=info &
WORKER_PID=$!
sleep 3
if ! kill -0 "$WORKER_PID" 2>/dev/null; then
    err "Celery worker failed to start."
    exit 1
fi

log "Starting Celery beat..."
ENVIRONMENT=development DEBUG=false OTEL_EXPORTER_OTLP_ENDPOINT= "$CELERY_BIN" -A app.workers.celery_app beat --loglevel=info &
BEAT_PID=$!
sleep 3
if ! kill -0 "$BEAT_PID" 2>/dev/null; then
    err "Celery beat failed to start."
    exit 1
fi

if [[ "$FRONTEND_MODE" == "dev" ]]; then
    log "Starting frontend with next dev..."
else
    log "Starting frontend with next start..."
fi

# Re-check the frontend port right before launch in case another process
# claimed it while backend and Celery were starting.
free_port "$FRONTEND_PORT"

cd "$FRONTEND_DIR"
if [[ "$FRONTEND_MODE" == "dev" ]]; then
    PORT="$FRONTEND_PORT" pnpm run dev &
else
    PORT="$FRONTEND_PORT" pnpm run start &
fi
FRONTEND_PID=$!

log "Waiting for frontend to be ready..."
for i in $(seq 1 45); do
    if curl -sf "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

# Give Next.js a brief stabilization window so we don't report success if it
# immediately exits after an early bind or startup error.
sleep 2

if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    err "Frontend failed to start."
    exit 1
fi

echo ""
log "═══════════════════════════════════════════════════"
log "  ✅ SphereVoice production-like local stack is running"
log ""
log "  🖥️  Frontend:      ${CYAN}http://localhost:$FRONTEND_PORT${NC}"
log "  🔧 Backend API:   ${CYAN}http://localhost:$BACKEND_PORT${NC}"
log "  📖 API Docs:      ${CYAN}http://localhost:$BACKEND_PORT/docs${NC}"
log "  🐘 PostgreSQL:    localhost:5434"
log "  🔴 Redis:         localhost:6382"
log "  ⚙️  Celery worker: running"
log "  ⏱️  Celery beat:   running"
log ""
warn "This is still not full production parity: external providers, LiveKit, Azure infra, and container runtime behavior may differ."
if [[ "$FRONTEND_MODE" == "dev" ]]; then
    warn "Frontend is running in dev mode, so Next.js watch/HMR behavior differs from production-like startup."
fi
log "Press Ctrl+C to stop app processes."
log "═══════════════════════════════════════════════════"

wait