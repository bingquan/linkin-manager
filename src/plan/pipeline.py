from __future__ import annotations

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


def _pick_pillars(cadence: int, allocations: dict[str, float], history: list[dict[str, Any]]) -> list[str]:
    ordered = [k for k, _ in sorted(allocations.items(), key=lambda x: x[1], reverse=True)]
    history_counts = Counter(r.get("pillar") for r in history[-12:])
    ordered = sorted(ordered, key=lambda p: (history_counts.get(p, 0), -allocations.get(p, 0)))
    pillars = ordered[: max(1, cadence)]

    if cadence >= 2 and len(set(pillars[:2])) == 1:
        for p in ordered:
            if p != pillars[0]:
                pillars[1] = p
                break

    return pillars[:cadence]


def _needs_systems_critique(selected_pillars: list[str]) -> bool:
    return not any(p in {"insight", "field"} for p in selected_pillars)


def build_week_plan(
    week_label: str,
    run_date: date,
    topics: list[dict[str, Any]],
    user_cfg: dict[str, Any],
    content_log: list[dict[str, Any]],
    out_path: Path,
) -> list[dict[str, Any]]:
    cadence = int(user_cfg.get("cadence", 2))
    allocations = user_cfg.get("pillars_allocation", {"insight": 0.3, "research_translation": 0.25})
    selected_pillars = _pick_pillars(cadence, allocations, content_log)

    if _needs_systems_critique(selected_pillars) and selected_pillars:
        selected_pillars[0] = "insight"

    posts: list[dict[str, Any]] = []
    used_ids: set[str] = set()

    for idx in range(cadence):
        pillar = selected_pillars[idx] if idx < len(selected_pillars) else "insight"
        chosen = None
        for topic in topics:
            t_id = topic.get("id")
            if not t_id or t_id in used_ids:
                continue
            if pillar == "research_translation" and topic.get("source_type") not in {"arxiv", "standard"}:
                continue
            chosen = topic
            break
        if chosen is None:
            for topic in topics:
                t_id = topic.get("id")
                if t_id and t_id not in used_ids:
                    chosen = topic
                    break

        if chosen is None:
            break

        used_ids.add(chosen["id"])
        posts.append(
            {
                "post_index": idx + 1,
                "pillar": pillar,
                "topic_id": chosen.get("id"),
                "topic_title": chosen.get("title"),
                "topic_url": chosen.get("url"),
                "theme_tags": chosen.get("theme_tags", []),
                "angle": _angle_for_pillar(pillar),
                "hook": _hook_for_topic(chosen, pillar),
                "cta": "What would you change in your deployment or eval stack based on this?",
                "requires_systems_critique": idx == 0,
            }
        )

    lines = [
        f"# Weekly Plan - {week_label}",
        "",
        f"Run date: {run_date.isoformat()}",
        f"Cadence: {cadence}",
        "",
    ]
    for post in posts:
        lines.extend(
            [
                f"## Post {post['post_index']:02d}",
                f"- Pillar: {post['pillar']}",
                f"- Topic: {post['topic_title']}",
                f"- Topic ID: {post['topic_id']}",
                f"- Angle: {post['angle']}",
                f"- Hook: {post['hook']}",
                f"- CTA: {post['cta']}",
                "",
            ]
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")

    return posts


def _angle_for_pillar(pillar: str) -> str:
    mapping = {
        "insight": "systems critique with second-order effects",
        "research_translation": "translate method detail into deployment implications",
        "field": "operational failure surface and mitigation",
        "leadership": "team/process decision pattern",
        "personal": "short reflection grounded in evidence",
    }
    return mapping.get(pillar, "systems critique with technical anchor")


def _hook_for_topic(topic: dict[str, Any], pillar: str) -> str:
    title = topic.get("title", "this week's signal")
    if pillar == "research_translation":
        return f"Most people will cite {title} for results. The real lesson is in the eval assumptions."
    if pillar == "field":
        return f"{title} looks strong on paper; production risk shows up one layer deeper."
    return f"If {title} is directionally right, most teams are still optimizing the wrong bottleneck."
