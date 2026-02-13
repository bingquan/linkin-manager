#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODEL_NAME="$(python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path('config/model.yaml').read_text()) or {}
print(cfg.get('model_name', 'Qwen/Qwen2.5-32B-Instruct-AWQ'))
PY
)"
TP_SIZE="$(python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path('config/model.yaml').read_text()) or {}
print(cfg.get('tensor_parallel_size', 2))
PY
)"

exec vllm serve "$MODEL_NAME" --tensor-parallel-size "$TP_SIZE"
