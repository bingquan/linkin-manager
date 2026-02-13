from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.common.io import read_jsonl, read_yaml, write_json
from src.common.llm import maybe_make_vllm_client
from src.common.time_utils import iso_week_label
from src.draft.pipeline import generate_draft, generate_references, write_draft_bundle
from src.evaluate.pipeline import quality_gate
from src.ingest.pipeline import run_ingest
from src.memory.pipeline import build_coverage_dashboard, update_content_log, update_topic_saturation
from src.plan.pipeline import build_week_plan
from src.rank.pipeline import filter_and_rank


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run weekly LinkedIn manager pipeline")
    parser.add_argument("--date", dest="run_date", help="Run date (YYYY-MM-DD). Defaults to today.")
    return parser.parse_args()


def _resolve_run_date(raw: str | None) -> date:
    if not raw:
        return date.today()
    return datetime.strptime(raw, "%Y-%m-%d").date()


def _topic_by_id(topics: list[dict[str, Any]], topic_id: str) -> dict[str, Any] | None:
    for t in topics:
        if t.get("id") == topic_id:
            return t
    return None


def _load_blacklist(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    args = parse_args()
    run_date = _resolve_run_date(args.run_date)
    week_label = iso_week_label(run_date)

    repo_root = Path(__file__).resolve().parent.parent
    cfg_dir = repo_root / "config"
    topics_dir = repo_root / "topics"
    weekly_dir = repo_root / "weekly" / week_label
    state_dir = repo_root / "state"

    user_cfg = read_yaml(cfg_dir / "user_profile.yaml")
    sources_cfg = read_yaml(cfg_dir / "sources.yaml")
    model_cfg = read_yaml(cfg_dir / "model.yaml")
    rubric_cfg = read_yaml(cfg_dir / "rubric.yaml")

    raw_dir = topics_dir / "RAW" / run_date.isoformat()
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_paths = run_ingest(str(raw_dir), run_date, sources_cfg, user_cfg)

    content_log_path = state_dir / "content_log.jsonl"
    content_log = read_jsonl(content_log_path)

    week_topics_dir = topics_dir / week_label
    filtered_path = week_topics_dir / "filtered_topics.jsonl"
    filter_report_path = week_topics_dir / "filter_report.md"

    ranked_topics = filter_and_rank(
        raw_paths=[Path(raw_paths["arxiv"]), Path(raw_paths["rss"]), Path(raw_paths["standards"])],
        content_log=content_log,
        user_cfg=user_cfg,
        run_date=run_date,
        out_topics_path=filtered_path,
        report_path=filter_report_path,
    )

    plan_path = weekly_dir / "plan.md"
    plan_posts = build_week_plan(
        week_label=week_label,
        run_date=run_date,
        topics=ranked_topics,
        user_cfg=user_cfg,
        content_log=content_log,
        out_path=plan_path,
    )

    drafts_dir = weekly_dir / "drafts"
    tone = user_cfg.get("tone", ["direct", "evaluative", "non-hype"])
    history_texts = []
    for rec in content_log[-10:]:
        dpath = repo_root / rec.get("draft_path", "")
        if dpath.exists():
            history_texts.append(dpath.read_text(encoding="utf-8"))

    blacklist = _load_blacklist(state_dir / "phrase_blacklist.txt")
    draft_paths: list[Path] = []

    runner_mode = model_cfg.get("runner_mode", "hosted")
    if runner_mode == "hosted":
        drafts_dir.mkdir(parents=True, exist_ok=True)
        for post in plan_posts:
            post_index = int(post["post_index"])
            placeholder = drafts_dir / f"post_{post_index:02d}.md"
            placeholder.write_text(
                "Hosted mode placeholder.\n\n"
                "Draft generation is intended for local or self-hosted runs.\n",
                encoding="utf-8",
            )
            write_json(
                drafts_dir / f"post_{post_index:02d}.references.json",
                {
                    "sources": [],
                    "evidence": [],
                    "confidence": "low",
                    "risk_flags": ["hosted_mode_no_draft_generation"],
                },
            )
            write_json(
                drafts_dir / f"post_{post_index:02d}_score.json",
                {
                    "scores": {
                        "systems_strategic": 0,
                        "technical_rigor": 0,
                        "clarity": 0,
                        "novelty": 0,
                    },
                    "passed": False,
                    "fail_reasons": ["hosted_mode_placeholder"],
                    "revision_count": 0,
                },
            )
            draft_paths.append(placeholder)
    else:
        llm_client = maybe_make_vllm_client(model_cfg)
        llm_available = bool(llm_client and llm_client.healthcheck())
        if llm_client and not llm_available:
            if bool(model_cfg.get("require_live_llm", False)):
                print("Error: vLLM endpoint unavailable and require_live_llm=true.")
                return 1
            print("Warning: vLLM endpoint unavailable; using deterministic fallback for this run.")
            llm_client = None

        for post in plan_posts:
            topic = _topic_by_id(ranked_topics, post.get("topic_id", ""))
            if topic is None:
                continue

            draft_text = generate_draft(
                post_spec=post,
                topic=topic,
                tone=tone,
                llm_client=llm_client,
                model_cfg=model_cfg,
            )
            references = generate_references(
                topic=topic,
                llm_client=llm_client,
                model_cfg=model_cfg,
            )
            draft_path, _ = write_draft_bundle(
                out_dir=drafts_dir,
                post_index=int(post["post_index"]),
                draft_text=draft_text,
                references=references,
            )

            quality_gate(
                draft_path=draft_path,
                references=references,
                rubric_cfg=rubric_cfg,
                blacklist_phrases=blacklist,
                history_texts=history_texts,
                llm_client=llm_client,
                model_cfg=model_cfg,
                max_revisions=2,
            )
            draft_paths.append(draft_path)

    update_content_log(
        content_log_path=content_log_path,
        run_date=run_date,
        week_label=week_label,
        plan_posts=plan_posts,
        draft_paths=draft_paths,
        phrase_blacklist=blacklist,
    )
    update_topic_saturation(state_dir / "topic_saturation.json", plan_posts)
    build_coverage_dashboard(
        dashboard_path=state_dir / "coverage_dashboard.md",
        content_log_path=content_log_path,
        allocations=user_cfg.get("pillars_allocation", {}),
        topic_saturation_path=state_dir / "topic_saturation.json",
    )

    print(f"Weekly pipeline complete for {week_label}")
    print(f"Plan: {plan_path}")
    print(f"Drafts: {drafts_dir}")
    print(f"Topics: {filtered_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
