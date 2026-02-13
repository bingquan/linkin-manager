# LinkedIn Manager Bot

Repo-native weekly pipeline for theme-driven LinkedIn planning and drafting with systems-level + technical-rigor constraints.

## What it produces

Per run week (`YYYY-Www`):
- `topics/<week>/filtered_topics.jsonl`
- `topics/<week>/filter_report.md`
- `weekly/<week>/plan.md`
- `weekly/<week>/drafts/post_XX.md`
- `weekly/<week>/drafts/post_XX.references.json`
- `weekly/<week>/drafts/post_XX_score.json`
- `state/content_log.jsonl`
- `state/coverage_dashboard.md`

## Config

- `config/user_profile.yaml`: themes, cadence, audience, pillar allocations, tone, constraints.
- `config/sources.yaml`: arXiv queries, RSS feeds, governance/security sources.
- `config/model.yaml`: `runner_mode: hosted|self_hosted`, model backend settings.
- `config/rubric.yaml`: scoring thresholds and reject rules.

## Run locally

```bash
./scripts/run_weekly.sh --date 2026-02-13
```

Date is optional; default is today.
For `self_hosted` + `vllm`, this script always:
- spins up the vLLM endpoint if needed,
- verifies endpoint health (`/v1/models`) before running,
- shuts down the endpoint after the pipeline finishes (only if the script started it).

## Runner modes

- `runner_mode: hosted`
  - Runs ingest/filter/rank/plan and writes draft placeholders + placeholder references/scores.
  - Intended for GitHub-hosted runners where local LLM inference is impractical.
- `runner_mode: self_hosted`
  - Runs full drafting + quality gate loop (up to 2 revisions).
  - This repo is intended to run with a live `vLLM` endpoint in self-hosted mode.
  - Uses OpenAI-compatible `vLLM` endpoint from `config/model.yaml` (`api_base`, `api_key`).
  - If `require_live_llm: true`, run fails when the endpoint is unavailable.

## vLLM startup (2 GPUs)

```bash
./scripts/run_vllm_server.sh
```

This reads:
- `model_name` from `config/model.yaml`
- `tensor_parallel_size` from `config/model.yaml` (default `2`)

Default endpoint expected by pipeline:
- `http://127.0.0.1:8000/v1`

## Weekly automation

GitHub workflow: `.github/workflows/weekly_update.yml`
- Cron: Mondays 00:00 UTC (08:00 Asia/Singapore)
- Runs pipeline
- Commits changes under `topics/`, `weekly/`, and `state/`

## Module map

- `src/ingest/pipeline.py`: arXiv/RSS/standards ingestion.
- `src/rank/pipeline.py`: freshness/credibility/theme filters + ranking.
- `src/plan/pipeline.py`: cadence and pillar-aware weekly planning.
- `src/draft/pipeline.py`: draft + references generation.
- `src/evaluate/pipeline.py`: rubric scoring, reject logic, revision loop.
- `src/memory/pipeline.py`: content log, saturation, dashboard updates.
- `src/run_weekly.py`: orchestrates end-to-end weekly run.
