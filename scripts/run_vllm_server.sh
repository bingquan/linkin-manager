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
GPU_MEM_UTIL="$(python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path('config/model.yaml').read_text()) or {}
print(cfg.get('gpu_memory_utilization', 0.75))
PY
)"
AUTO_SELECT_GPUS="$(python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path('config/model.yaml').read_text()) or {}
print(str(cfg.get('auto_select_gpus', True)).lower())
PY
)"
MAX_MODEL_LEN="$(python3 - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path('config/model.yaml').read_text()) or {}
print(cfg.get('context_length', 8192))
PY
)"

if [[ -z "${CUDA_VISIBLE_DEVICES:-}" && "$AUTO_SELECT_GPUS" == "true" ]]; then
  CUDA_VISIBLE_DEVICES="$(python3 - <<'PY'
import subprocess
import yaml
from pathlib import Path

cfg = yaml.safe_load(Path('config/model.yaml').read_text()) or {}
tp = int(cfg.get('tensor_parallel_size', 2))
out = subprocess.check_output(
    ["nvidia-smi", "--query-gpu=index,memory.used", "--format=csv,noheader,nounits"],
    text=True,
)
rows = []
for line in out.strip().splitlines():
    idx_s, used_s = [x.strip() for x in line.split(",")]
    rows.append((int(idx_s), int(used_s)))
rows.sort(key=lambda x: x[1])
picked = [str(idx) for idx, _ in rows[:tp]]
print(",".join(picked))
PY
)"
  export CUDA_VISIBLE_DEVICES
  echo "Auto-selected CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES}"
fi

exec vllm serve "$MODEL_NAME" \
  --tensor-parallel-size "$TP_SIZE" \
  --gpu-memory-utilization "$GPU_MEM_UTIL" \
  --max-model-len "$MAX_MODEL_LEN"
