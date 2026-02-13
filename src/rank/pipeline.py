from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from src.common.io import read_jsonl, write_jsonl


CRED_ORDER = {"A": 3, "B": 2, "C": 1}


def _parse_date(s: str, fallback: date) -> date:
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except Exception:
        return fallback


def _keyword_score(text: str, keywords: list[str]) -> float:
    lowered = text.lower()
    hits = sum(1 for k in keywords if k.lower() in lowered)
    if not keywords:
        return 0.0
    return min(1.0, hits / max(1, len(keywords)))


def _history_topic_ids(content_log: list[dict[str, Any]], n: int) -> set[str]:
    rows = content_log[-n:]
    return {r.get("topic_id", "") for r in rows if r.get("topic_id")}


def _novelty_score(topic: dict[str, Any], recent_topic_ids: set[str], recent_claims: set[str]) -> float:
    if topic.get("id") in recent_topic_ids:
        return 0.0
    claims = set(topic.get("key_claims") or [])
    overlap = len(claims & recent_claims)
    if not claims:
        return 0.8
    return max(0.0, 1.0 - overlap / max(1, len(claims)))


def _strategic_leverage_score(text: str) -> float:
    keywords = [
        "incentive",
        "governance",
        "deployment",
        "failure mode",
        "evaluation",
        "risk",
        "policy",
        "threat model",
    ]
    return _keyword_score(text, keywords)


def filter_and_rank(
    raw_paths: list[Path],
    content_log: list[dict[str, Any]],
    user_cfg: dict[str, Any],
    run_date: date,
    out_topics_path: Path,
    report_path: Path,
) -> list[dict[str, Any]]:
    all_topics: list[dict[str, Any]] = []
    for path in raw_paths:
        all_topics.extend(read_jsonl(path))

    freshness_days = int(user_cfg.get("freshness_days", 14))
    min_tier = str(user_cfg.get("min_credibility_tier", "B")).upper()
    top_k = int(user_cfg.get("top_k_topics", 30))
    themes = user_cfg.get("themes", [])
    history_window = int(user_cfg.get("history_window_posts", 10))

    min_date = run_date - timedelta(days=freshness_days)
    recent_ids = _history_topic_ids(content_log, history_window)
    recent_claims = {
        claim
        for row in content_log[-history_window:]
        for claim in row.get("claims", [])
        if isinstance(claim, str)
    }

    filtered: list[dict[str, Any]] = []
    dropped = {"freshness": 0, "credibility": 0, "theme": 0}

    for t in all_topics:
        published = _parse_date(str(t.get("published_at", "")), run_date)
        if published < min_date:
            dropped["freshness"] += 1
            continue

        tier = str(t.get("credibility_tier", "C")).upper()
        if CRED_ORDER.get(tier, 0) < CRED_ORDER.get(min_tier, 0):
            dropped["credibility"] += 1
            continue

        text = f"{t.get('title', '')} {t.get('summary', '')}".lower()
        theme_tags = t.get("theme_tags") or []
        if not theme_tags:
            theme_tags = [th for th in themes if th.replace("_", " ") in text or th in text]
            t["theme_tags"] = theme_tags
        if not theme_tags:
            dropped["theme"] += 1
            continue

        relevance = _keyword_score(text, [x.replace("_", " ") for x in themes])
        novelty = _novelty_score(t, recent_ids, recent_claims)
        strategic = _strategic_leverage_score(text)
        credibility = CRED_ORDER.get(tier, 1) / 3.0

        score = round(
            0.35 * relevance + 0.25 * novelty + 0.25 * strategic + 0.15 * credibility,
            4,
        )

        t["scores"] = {
            "relevance": round(relevance, 4),
            "novelty": round(novelty, 4),
            "strategic_leverage": round(strategic, 4),
            "credibility": round(credibility, 4),
            "composite": score,
        }
        filtered.append(t)

    ranked = sorted(filtered, key=lambda x: x.get("scores", {}).get("composite", 0.0), reverse=True)
    selected = ranked[:top_k]

    write_jsonl(out_topics_path, selected)

    report_lines = [
        "# Filter Report",
        "",
        f"Run date: {run_date.isoformat()}",
        f"Input topics: {len(all_topics)}",
        f"Selected topics: {len(selected)}",
        "",
        "## Dropped",
        f"- Freshness: {dropped['freshness']}",
        f"- Credibility: {dropped['credibility']}",
        f"- Theme mismatch: {dropped['theme']}",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    return selected
