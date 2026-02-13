# AGENTS.md

## Runtime requirement

- This repository is intended to run with a live `vLLM` endpoint in `self_hosted` mode.
- `./scripts/run_weekly.sh` must always ensure vLLM lifecycle in `self_hosted` mode:
  - spin up endpoint if missing,
  - verify health before pipeline execution,
  - close endpoint when finished (if this script started it).
- Default endpoint used by the pipeline is configured in `config/model.yaml`:
  - `api_base: http://127.0.0.1:8000/v1`
- To enforce this strictly, set:
  - `require_live_llm: true` in `config/model.yaml`

## Notes

- `runner_mode: hosted` is allowed for CI/planning-only workflows.
- `runner_mode: self_hosted` should be treated as LLM-backed generation/evaluation mode.
