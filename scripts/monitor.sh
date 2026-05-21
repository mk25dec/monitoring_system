#!/usr/bin/env bash
# Start / stop / status for the full monitoring stack (Redis + ingest + dashboard).
#
# Usage:
#   ./scripts/monitor.sh start
#   ./scripts/monitor.sh stop
#   ./scripts/monitor.sh status
#   ./scripts/monitor.sh restart

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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
    echo "ERROR: pixi not found. Install from https://pixi.sh"
    exit 1
  fi
}

redis_ping() {
  if command -v redis-cli >/dev/null 2>&1; then
    redis-cli -h 127.0.0.1 -p 6379 ping 2>/dev/null | grep -q PONG
  else
    pixi run python -c "import redis; redis.Redis(host='127.0.0.1',port=6379).ping()" 2>/dev/null
  fi
}

docker_ok() {
  command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

start_redis() {
  if redis_ping; then
    if docker_ok && docker compose -f "${ROOT}/docker-compose.yml" ps redis 2>/dev/null | grep -q running; then
      echo "redis" > "${REDIS_MODE}"
      echo "[redis] Already running (Docker)."
    else
      echo "system" > "${REDIS_MODE}"
      echo "[redis] Already running (system)."
    fi
    return 0
  fi

  if docker_ok; then
    echo "[redis] Starting via Docker..."
    docker compose -f "${ROOT}/docker-compose.yml" up -d redis
    echo "docker" > "${REDIS_MODE}"
    for _ in $(seq 1 20); do
      if redis_ping; then
        echo "[redis] Ready."
        return 0
      fi
      sleep 0.5
    done
    echo "ERROR: Redis Docker container did not respond."
    exit 1
  fi

  if command -v systemctl >/dev/null 2>&1; then
    echo "[redis] Trying systemctl start redis-server..."
    sudo systemctl start redis-server 2>/dev/null || systemctl start redis 2>/dev/null || true
  fi

  if redis_ping; then
    echo "system" > "${REDIS_MODE}"
    echo "[redis] Ready (system)."
    return 0
  fi

  echo "ERROR: Redis is not running. Install Redis or start Docker, then retry."
  exit 1
}

stop_redis() {
  local mode=""
  [[ -f "${REDIS_MODE}" ]] && mode="$(cat "${REDIS_MODE}")"
  if [[ "${mode}" == "docker" ]] && docker_ok; then
    echo "[redis] Stopping Docker Redis..."
    docker compose -f "${ROOT}/docker-compose.yml" stop redis 2>/dev/null || true
  else
    echo "[redis] Left running (system Redis was used or unknown)."
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
    echo "[${name}] Stopping PID ${pid}..."
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
    echo "[ingest] Already running (PID $(cat "${INGEST_PID}"))."
    return 0
  fi
  echo "[ingest] Starting..."
  nohup pixi run ingest >> "${INGEST_LOG}" 2>&1 &
  echo $! > "${INGEST_PID}"
  sleep 1
  if is_running "${INGEST_PID}"; then
    echo "[ingest] Running (PID $(cat "${INGEST_PID}")). Log: ${INGEST_LOG}"
  else
    echo "ERROR: Ingest failed to start. See ${INGEST_LOG}"
    tail -20 "${INGEST_LOG}" 2>/dev/null || true
    exit 1
  fi
}

start_dashboard() {
  if is_running "${DASH_PID}"; then
    echo "[dashboard] Already running (PID $(cat "${DASH_PID}"))."
    echo "[dashboard] Open ${DASH_URL}"
    return 0
  fi
  echo "[dashboard] Starting..."
  nohup pixi run dashboard >> "${DASH_LOG}" 2>&1 &
  echo $! > "${DASH_PID}"
  sleep 2
  if is_running "${DASH_PID}"; then
    echo "[dashboard] Running (PID $(cat "${DASH_PID}")). Log: ${DASH_LOG}"
    echo "[dashboard] Open ${DASH_URL}"
  else
    echo "ERROR: Dashboard failed to start. See ${DASH_LOG}"
    tail -20 "${DASH_LOG}" 2>/dev/null || true
    exit 1
  fi
}

cmd_start() {
  need_pixi
  echo "=== Starting Stage Monitor ==="
  start_redis
  echo "[db] Initializing schema..."
  pixi run init-db
  start_ingest
  start_dashboard
  echo ""
  echo "=== Started ==="
  echo "  Dashboard: ${DASH_URL}"
  echo "  Stop all:  ./scripts/monitor.sh stop"
  echo "  Status:    ./scripts/monitor.sh status"
}

cmd_stop() {
  echo "=== Stopping Stage Monitor ==="
  stop_pid "dashboard" "${DASH_PID}"
  stop_pid "ingest" "${INGEST_PID}"
  stop_redis
  # Fallback: stray processes from this project
  pkill -f "stage-ingest" 2>/dev/null || true
  pkill -f "streamlit run src/monitoring_system/dashboard/app.py" 2>/dev/null || true
  echo "=== Stopped ==="
}

cmd_status() {
  echo "=== Stage Monitor status ==="
  if redis_ping; then
    echo "[redis]     running"
  else
    echo "[redis]     stopped"
  fi
  if is_running "${INGEST_PID}"; then
    echo "[ingest]    running (PID $(cat "${INGEST_PID}"))"
  else
    echo "[ingest]    stopped"
  fi
  if is_running "${DASH_PID}"; then
    echo "[dashboard] running (PID $(cat "${DASH_PID}")) → ${DASH_URL}"
  else
    echo "[dashboard] stopped"
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
