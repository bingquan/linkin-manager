#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

RUNNER_MODE="$(python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path('config/model.yaml').read_text()) or {}
print(cfg.get('runner_mode', 'hosted'))
PY
)"
BACKEND="$(python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path('config/model.yaml').read_text()) or {}
print(cfg.get('backend', ''))
PY
)"
API_BASE="$(python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path('config/model.yaml').read_text()) or {}
print(cfg.get('api_base', 'http://127.0.0.1:8000/v1').rstrip('/'))
PY
)"
STARTUP_TIMEOUT_SECONDS="$(python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path('config/model.yaml').read_text()) or {}
print(int(cfg.get('startup_timeout_seconds', 900)))
PY
)"
HEALTH_URL="${API_BASE}/models"
STARTED_VLLM=0
VLLM_PID=""

cleanup() {
  if [[ "$STARTED_VLLM" -eq 1 && -n "${VLLM_PID}" ]]; then
    if kill -0 "$VLLM_PID" >/dev/null 2>&1; then
      echo "Stopping vLLM server (pid=${VLLM_PID})"
      kill "$VLLM_PID" || true
      wait "$VLLM_PID" 2>/dev/null || true
    fi
  fi
}
trap cleanup EXIT

ensure_vllm_ready() {
  if curl -sSf "$HEALTH_URL" >/dev/null 2>&1; then
    echo "vLLM healthcheck passed at ${HEALTH_URL} (existing endpoint)"
    return 0
  fi

  echo "Starting vLLM endpoint for self-hosted pipeline..."
  mkdir -p state
  ./scripts/run_vllm_server.sh > state/vllm_server.log 2>&1 &
  VLLM_PID="$!"
  STARTED_VLLM=1

  checks=$(( STARTUP_TIMEOUT_SECONDS / 2 ))
  if [[ "$checks" -lt 1 ]]; then
    checks=1
  fi
  for _ in $(seq 1 "$checks"); do
    if curl -sSf "$HEALTH_URL" >/dev/null 2>&1; then
      echo "vLLM healthcheck passed at ${HEALTH_URL}"
      return 0
    fi
    if [[ "$STARTED_VLLM" -eq 1 && -n "${VLLM_PID}" ]] && ! kill -0 "$VLLM_PID" >/dev/null 2>&1; then
      echo "vLLM process exited before healthcheck. See state/vllm_server.log"
      return 1
    fi
    sleep 2
  done

  echo "vLLM failed healthcheck at ${HEALTH_URL}. See state/vllm_server.log"
  return 1
}

if [[ "$RUNNER_MODE" == "self_hosted" && "${BACKEND,,}" == "vllm" ]]; then
  ensure_vllm_ready
fi

python3 -m pip install -r requirements.txt
python3 -m src.run_weekly "$@"
