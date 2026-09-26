#!/usr/bin/env bash
#
# SatQuery AI — one-command startup (Linux / macOS)
#
# Brings up the full stack unattended:
#   1. PostGIS + satquery-service via docker compose
#   2. GeoChat-7B inference (see "Execution modes" below)
#   3. Polls GET /health until geochat_loaded:true, failing loudly on timeout
#   4. Prints a single "System Ready" banner
#
# ─── Execution modes ──────────────────────────────────────────────────────────
# GeoChat has no standalone inference server — geochat_engine.py loads the model
# *in-process* inside whatever runs main:app.  Two consequences:
#
#   host   – satquery-service runs on the host inside ml/geochat/venv, so it can
#            see the NVIDIA GPU and /health reports geochat_loaded:true.
#            PostGIS still runs in Docker.  Chosen automatically when the venv
#            exists AND torch reports CUDA available.
#
#   docker – satquery-service runs in its container.  ml/ is outside the image's
#            build context, so the geochat package is absent and /health always
#            reports degraded.  Everything except VQA/grounding works: STAC
#            ingestion, deterministic metrics, PostGIS history, alerting.
#
# Override with SATQUERY_MODE=host|docker.
# On a machine with no GPU, set SKIP_GEOCHAT_GATE=1 to treat a degraded service
# as success instead of failing at the 90s gate.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

HEALTH_URL="${HEALTH_URL:-http://localhost:8082/health}"
GEOCHAT_TIMEOUT="${GEOCHAT_TIMEOUT:-90}"
SKIP_GEOCHAT_GATE="${SKIP_GEOCHAT_GATE:-0}"
LOG_DIR="$REPO_ROOT/logs"
INFERENCE_LOG="$LOG_DIR/geochat-inference.log"
INFERENCE_PID_FILE="$LOG_DIR/geochat-inference.pid"

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'
BLUE=$'\033[0;34m'; BOLD=$'\033[1m'; NC=$'\033[0m'

log()  { printf '%s[start]%s %s\n' "$BLUE" "$NC" "$*"; }
warn() { printf '%s[warn]%s  %s\n' "$YELLOW" "$NC" "$*"; }
die() {
    printf '\n%s%s╔══════════════════════════════════════════════════════════════╗%s\n' "$BOLD" "$RED" "$NC"
    printf '%s%s║  STARTUP FAILED                                              ║%s\n' "$BOLD" "$RED" "$NC"
    printf '%s%s╚══════════════════════════════════════════════════════════════╝%s\n' "$BOLD" "$RED" "$NC"
    printf '%s\n' "$*" >&2
    exit 1
}

# ─── 1. Preflight ─────────────────────────────────────────────────────────────
command -v docker >/dev/null 2>&1 || die "docker not found on PATH. Install Docker Desktop, Colima, or OrbStack first."
docker info >/dev/null 2>&1 || die "The Docker daemon is not responding. Start Docker Desktop (or run: colima start) and retry."
docker compose version >/dev/null 2>&1 || die "The 'docker compose' plugin is unavailable. Install docker-compose v2+."
command -v curl >/dev/null 2>&1 || die "curl not found on PATH; it is required for the /health gate."
command -v python3 >/dev/null 2>&1 || die "python3 not found on PATH; it is required to parse the /health response."

mkdir -p "$LOG_DIR"

# ─── 2. Decide execution mode ─────────────────────────────────────────────────
VENV_PY="$REPO_ROOT/ml/geochat/venv/bin/python"
[ -x "$VENV_PY" ] || VENV_PY="$REPO_ROOT/ml/geochat/venv/Scripts/python.exe"   # Git-Bash on Windows

detect_mode() {
    if [ -n "${SATQUERY_MODE:-}" ]; then
        echo "$SATQUERY_MODE"; return
    fi
    if [ -x "$VENV_PY" ] && "$VENV_PY" -c 'import torch,sys; sys.exit(0 if torch.cuda.is_available() else 1)' >/dev/null 2>&1; then
        echo "host"
    else
        echo "docker"
    fi
}
MODE="$(detect_mode)"
log "Execution mode: ${BOLD}${MODE}${NC}"

# ─── 3. Bring up containers ───────────────────────────────────────────────────
if [ "$MODE" = "host" ]; then
    log "Starting PostGIS (satquery-service will run on the host for GPU access)..."
    docker compose up -d postgis
else
    log "Starting PostGIS + satquery-service..."
    docker compose up -d postgis satquery-service
fi

log "Waiting for PostGIS to report healthy..."
PG_CONTAINER="$(docker compose ps -q postgis)"
[ -n "$PG_CONTAINER" ] || die "PostGIS container failed to start. Inspect: docker compose logs postgis"
for _ in $(seq 1 60); do
    state="$(docker inspect -f '{{.State.Health.Status}}' "$PG_CONTAINER" 2>/dev/null || echo starting)"
    [ "$state" = "healthy" ] && break
    sleep 2
done
[ "${state:-}" = "healthy" ] || die "PostGIS did not become healthy within 120s. Inspect: docker compose logs postgis"
log "PostGIS healthy."

# ─── 4. Launch host-side GeoChat inference ────────────────────────────────────
if [ "$MODE" = "host" ]; then
    # Reap a previous run so re-running the script never double-binds :8082
    if [ -f "$INFERENCE_PID_FILE" ] && kill -0 "$(cat "$INFERENCE_PID_FILE")" 2>/dev/null; then
        log "Stopping previous inference process (PID $(cat "$INFERENCE_PID_FILE"))..."
        kill "$(cat "$INFERENCE_PID_FILE")" 2>/dev/null || true
        sleep 2
    fi
    [ -x "$VENV_PY" ] || die "SATQUERY_MODE=host but no GeoChat venv at ml/geochat/venv. See ml/geochat/SETUP.md."

    log "Launching GeoChat inference in the background (log: ${INFERENCE_LOG})..."
    (
        cd "$REPO_ROOT/satquery-service"
        SATQUERY_DATABASE_URL="${SATQUERY_DATABASE_URL:-postgresql://orbital_user:orbital_password@localhost:5432/orbital_db}" \
        nohup "$VENV_PY" -m uvicorn main:app --host 0.0.0.0 --port 8082 \
            > "$INFERENCE_LOG" 2>&1 &
        echo $! > "$INFERENCE_PID_FILE"
    )
    log "Inference PID $(cat "$INFERENCE_PID_FILE")."
fi

# ─── 5. Health gate ───────────────────────────────────────────────────────────
log "Polling ${HEALTH_URL} (timeout ${GEOCHAT_TIMEOUT}s)..."

read_field() {  # read_field <json> <key>
    printf '%s' "$1" | python3 -c "import json,sys
try:
    print(json.load(sys.stdin).get('$2', ''))
except Exception:
    print('')" 2>/dev/null || printf ''
}

deadline=$(( $(date +%s) + GEOCHAT_TIMEOUT ))
body=""; loaded=""; reachable=0
while [ "$(date +%s)" -lt "$deadline" ]; do
    if body="$(curl -sf --max-time 5 "$HEALTH_URL" 2>/dev/null)"; then
        reachable=1
        loaded="$(read_field "$body" geochat_loaded)"
        [ "$loaded" = "True" ] || [ "$loaded" = "true" ] && break
        [ "$SKIP_GEOCHAT_GATE" = "1" ] && break
    fi
    sleep 3
done

if [ "$reachable" != "1" ]; then
    if [ "$MODE" = "host" ]; then
        warn "Last 20 lines of ${INFERENCE_LOG}:"; tail -20 "$INFERENCE_LOG" 2>/dev/null || true
    else
        warn "Last 20 lines of satquery-service:"; docker compose logs --tail 20 satquery-service 2>&1 || true
    fi
    die "The service never answered ${HEALTH_URL} within ${GEOCHAT_TIMEOUT}s."
fi

if [ "$loaded" != "True" ] && [ "$loaded" != "true" ]; then
    geochat_error="$(read_field "$body" geochat_error)"
    if [ "$SKIP_GEOCHAT_GATE" = "1" ]; then
        warn "GeoChat NOT loaded — continuing because SKIP_GEOCHAT_GATE=1."
        warn "  Reason: ${geochat_error:-unknown}"
        warn "  VQA and grounding are unavailable. STAC ingestion, deterministic"
        warn "  metrics, PostGIS history and alerting all work normally."
    else
        printf '\n'
        warn "Service is UP but reports geochat_loaded=false after ${GEOCHAT_TIMEOUT}s."
        warn "  geochat_error: ${geochat_error:-unknown}"
        if [ "$MODE" = "docker" ]; then
            warn "  Cause: in docker mode the geochat package is not in the image"
            warn "  (ml/ sits outside the build context), so it can never load."
            warn "  Fix: set up ml/geochat/venv per ml/geochat/SETUP.md and re-run,"
            warn "  or re-run with SKIP_GEOCHAT_GATE=1 to accept degraded mode."
        else
            warn "  Inspect: tail -50 ${INFERENCE_LOG}"
        fi
        die "GeoChat failed to load within ${GEOCHAT_TIMEOUT}s (see above)."
    fi
fi

# ─── 6. Ready banner ──────────────────────────────────────────────────────────
status="$(read_field "$body" status)"
vram="$(read_field "$body" peak_vram_gb)"
printf '\n%s%s╔══════════════════════════════════════════════════════════════╗%s\n' "$BOLD" "$GREEN" "$NC"
printf '%s%s║                       SYSTEM READY                           ║%s\n' "$BOLD" "$GREEN" "$NC"
printf '%s%s╚══════════════════════════════════════════════════════════════╝%s\n' "$BOLD" "$GREEN" "$NC"
printf '  %-22s %s\n' "Frontend (dev)"  "http://localhost:8080"
printf '  %-22s %s\n' "Frontend (docker)" "http://localhost:5173"
printf '  %-22s %s\n' "API"             "http://localhost:8082"
printf '  %-22s %s\n' "Health"          "$HEALTH_URL"
printf '  %-22s %s\n' "Alerts"          "http://localhost:8082/api/alerts"
printf '  %-22s %s\n' "PostGIS"         "postgresql://orbital_user:***@localhost:5432/orbital_db"
printf '\n'
printf '  %-22s %s\n' "Mode"            "$MODE"
printf '  %-22s %s\n' "Service status"  "${status:-unknown}"
printf '  %-22s %s\n' "GeoChat loaded"  "${loaded:-false}"
[ -n "$vram" ] && [ "$vram" != "0.0" ] && printf '  %-22s %s GB\n' "Peak VRAM" "$vram"
[ "$MODE" = "host" ] && printf '  %-22s %s\n' "Inference log" "$INFERENCE_LOG"
printf '\n'
