from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from src.common.io import append_jsonl, read_json, read_jsonl, write_json, write_jsonl


def extract_repeated_phrases(text: str, phrase_blacklist: list[str]) -> list[str]:
    lowered = text.lower()
    return [p for p in phrase_blacklist if p.lower() in lowered]


def update_content_log(
    content_log_path: Path,
    run_date: date,
    week_label: str,
    plan_posts: list[dict[str, Any]],
    draft_paths: list[Path],
    phrase_blacklist: list[str],
) -> list[dict[str, Any]]:
    records = []
    root = content_log_path.resolve().parent.parent
    for plan_item, draft_path in zip(plan_posts, draft_paths):
        draft_text = draft_path.read_text(encoding="utf-8")
        try:
            draft_path_str = str(draft_path.resolve().relative_to(root))
        except ValueError:
            draft_path_str = str(draft_path)
        record = {
            "date": run_date.isoformat(),
            "week": week_label,
            "status": "planned",
            "pillar": plan_item.get("pillar"),
            "themes": plan_item.get("theme_tags", []),
            "topic_id": plan_item.get("topic_id"),
            "hook_type": "framework" if "framework" in plan_item.get("hook", "").lower() else "translation",
            "claims": [line for line in draft_text.splitlines() if line.lower().startswith("core claim:")],
            "repeated_phrase_flags": extract_repeated_phrases(draft_text, phrase_blacklist),
            "draft_path": draft_path_str,
        }
        append_jsonl(content_log_path, record)
        records.append(record)
    return records


def update_topic_saturation(topic_saturation_path: Path, plan_posts: list[dict[str, Any]]) -> dict[str, int]:
    data = read_json(topic_saturation_path, default={})
    if not isinstance(data, dict):
        data = {}
    for post in plan_posts:
        for theme in post.get("theme_tags", []):
            data[theme] = int(data.get(theme, 0)) + 1
    write_json(topic_saturation_path, data)
    return {k: int(v) for k, v in data.items()}


def build_coverage_dashboard(
    dashboard_path: Path,
    content_log_path: Path,
    allocations: dict[str, float],
    topic_saturation_path: Path,
) -> None:
    logs = read_jsonl(content_log_path)
    sat = read_json(topic_saturation_path, default={})
    pillar_counts = Counter(row.get("pillar", "unknown") for row in logs)
    total = sum(pillar_counts.values())

    lines = [
        "# Coverage Dashboard",
        "",
        f"Total tracked posts: {total}",
        "",
        "## Pillar Coverage",
    ]
    for pillar, target in allocations.items():
        count = pillar_counts.get(pillar, 0)
        pct = (count / total) if total else 0.0
        lines.append(f"- {pillar}: {count} ({pct:.1%}) vs target {target:.0%}")

    lines.append("")
    lines.append("## Repetition Alerts")
    repeated = [row for row in logs[-20:] if row.get("repeated_phrase_flags")]
    if not repeated:
        lines.append("- None")
    else:
        lines.append(f"- {len(repeated)} recent posts with phrase warnings")

    lines.append("")
    lines.append("## Theme Saturation")
    if sat:
        for theme, count in sorted(sat.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- {theme}: {count}")
    else:
        lines.append("- No data")

    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
