#!/usr/bin/env bash
# Start / stop the full Stage Monitor (Docker Redis + ingest + dashboard).
#
# Usage:
#   ./scripts/monitor.sh start    # first time: installs deps, starts Docker Redis, opens stack
#   ./scripts/monitor.sh stop     # stops dashboard, ingest, and Docker Redis (if we started it)
#   ./scripts/monitor.sh status
#   ./scripts/monitor.sh restart

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${ROOT}/docker-compose.yml"
RUN_DIR="${ROOT}/.run"
INGEST_PID="${RUN_DIR}/ingest.pid"
DASH_PID="${RUN_DIR}/dashboard.pid"
REDIS_MODE="${RUN_DIR}/redis.mode"
INGEST_LOG="${RUN_DIR}/ingest.log"
DASH_LOG="${RUN_DIR}/dashboard.log"
DASH_URL="http://localhost:8501"

cd "${ROOT}"
mkdir -p "${RUN_DIR}"

need_pixi() {
  if ! command -v pixi >/dev/null 2>&1; then
    echo ""
    echo "ERROR: Pixi is not installed."
    echo "  Install from https://pixi.sh then open a new terminal and run: ./start"
    echo ""
    exit 1
  fi
}

need_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo ""
    echo "ERROR: Docker is not installed."
    echo "  Install Docker Desktop (or Docker Engine), start it, then run: ./start"
    echo ""
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    echo ""
    echo "ERROR: Docker is installed but not running."
    echo "  Open Docker Desktop and wait until it is ready, then run: ./start"
    echo ""
    exit 1
  fi
}

ensure_pixi_env() {
  if [[ ! -d "${ROOT}/.pixi/envs/default" ]]; then
    echo "[setup] First time — installing software (may take a few minutes)..."
    pixi install
    echo "[setup] Done."
  fi
}

redis_ping() {
  if command -v redis-cli >/dev/null 2>&1; then
    redis-cli -h 127.0.0.1 -p 6379 ping 2>/dev/null | grep -q PONG
  else
    pixi run python -c "import redis; redis.Redis(host='127.0.0.1',port=6379).ping()" 2>/dev/null
  fi
}

compose_running() {
  docker compose -f "${COMPOSE_FILE}" ps --status running 2>/dev/null | grep -q redis
}

start_redis() {
  need_docker

  if redis_ping && compose_running; then
    echo "docker" > "${REDIS_MODE}"
    echo "[redis] Already running (Docker)."
    return 0
  fi

  if redis_ping && ! compose_running; then
    echo "external" > "${REDIS_MODE}"
    echo "[redis] Already running (not started by this script — left as-is on stop)."
    return 0
  fi

  echo "[redis] Starting database (Docker)..."
  docker compose -f "${COMPOSE_FILE}" up -d
  echo "docker" > "${REDIS_MODE}"

  for _ in $(seq 1 30); do
    if redis_ping; then
      echo "[redis] Ready."
      return 0
    fi
    sleep 0.5
  done

  echo "ERROR: Redis did not start. Is Docker running? Try: docker compose -f docker-compose.yml logs"
  exit 1
}

stop_redis() {
  local mode=""
  [[ -f "${REDIS_MODE}" ]] && mode="$(cat "${REDIS_MODE}")"
  if [[ "${mode}" == "docker" ]]; then
    echo "[redis] Stopping database (Docker)..."
    docker compose -f "${COMPOSE_FILE}" down
  elif [[ "${mode}" == "external" ]]; then
    echo "[redis] Left running (was already up before start)."
  else
    echo "[redis] Nothing to stop."
  fi
  rm -f "${REDIS_MODE}"
}

is_running() {
  local pid_file="$1"
  [[ -f "${pid_file}" ]] || return 1
  local pid
  pid="$(cat "${pid_file}")"
  kill -0 "${pid}" 2>/dev/null
}

stop_pid() {
  local name="$1"
  local pid_file="$2"
  if is_running "${pid_file}"; then
    local pid
    pid="$(cat "${pid_file}")"
    echo "[${name}] Stopping..."
    kill "${pid}" 2>/dev/null || true
    for _ in $(seq 1 10); do
      kill -0 "${pid}" 2>/dev/null || break
      sleep 0.3
    done
    if kill -0 "${pid}" 2>/dev/null; then
      kill -9 "${pid}" 2>/dev/null || true
    fi
  fi
  rm -f "${pid_file}"
}

start_ingest() {
  if is_running "${INGEST_PID}"; then
    echo "[ingest] Already running."
    return 0
  fi
  echo "[ingest] Starting..."
  nohup pixi run ingest >> "${INGEST_LOG}" 2>&1 &
  echo $! > "${INGEST_PID}"
  sleep 1
  if is_running "${INGEST_PID}"; then
    echo "[ingest] Running."
  else
    echo "ERROR: Ingest failed. See ${INGEST_LOG}"
    tail -15 "${INGEST_LOG}" 2>/dev/null || true
    exit 1
  fi
}

start_dashboard() {
  if is_running "${DASH_PID}"; then
    echo "[dashboard] Already running → ${DASH_URL}"
    return 0
  fi
  echo "[dashboard] Starting..."
  nohup pixi run dashboard >> "${DASH_LOG}" 2>&1 &
  echo $! > "${DASH_PID}"
  sleep 2
  if is_running "${DASH_PID}"; then
    echo "[dashboard] Running → ${DASH_URL}"
  else
    echo "ERROR: Dashboard failed. See ${DASH_LOG}"
    tail -15 "${DASH_LOG}" 2>/dev/null || true
    exit 1
  fi
}

cmd_start() {
  need_pixi
  ensure_pixi_env
  echo "=== Starting Stage Monitor ==="
  start_redis
  echo "[db] Preparing local database..."
  pixi run init-db
  start_ingest
  start_dashboard
  echo ""
  echo "=== Ready ==="
  echo "  Open in your browser: ${DASH_URL}"
  echo "  Try a demo job:        pixi run sample-etl"
  echo "  Stop everything:       ./stop"
  echo ""
}

cmd_stop() {
  echo "=== Stopping Stage Monitor ==="
  stop_pid "dashboard" "${DASH_PID}"
  stop_pid "ingest" "${INGEST_PID}"
  stop_redis
  pkill -f "stage-ingest" 2>/dev/null || true
  pkill -f "streamlit run src/monitoring_system/dashboard/app.py" 2>/dev/null || true
  echo ""
  echo "=== Stopped ==="
  echo "  Start again anytime: ./start"
  echo ""
}

cmd_status() {
  echo "=== Stage Monitor ==="
  if redis_ping; then
    echo "  Redis:     running"
  else
    echo "  Redis:     stopped"
  fi
  if is_running "${INGEST_PID}"; then
    echo "  Ingest:    running"
  else
    echo "  Ingest:    stopped"
  fi
  if is_running "${DASH_PID}"; then
    echo "  Dashboard: running → ${DASH_URL}"
  else
    echo "  Dashboard: stopped"
  fi
}

cmd_restart() {
  cmd_stop
  sleep 1
  cmd_start
}

case "${1:-}" in
  start)   cmd_start ;;
  stop)    cmd_stop ;;
  status)  cmd_status ;;
  restart) cmd_restart ;;
  *)
    echo "Usage: $0 {start|stop|status|restart}"
    exit 1
    ;;
esac
