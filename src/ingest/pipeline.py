from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import feedparser

from src.common.io import write_jsonl
from src.common.time_utils import iso_date


ARXIV_API = "http://export.arxiv.org/api/query"


def _credibility_from_url(url: str) -> str:
    u = url.lower()
    if any(k in u for k in ["arxiv.org", "nist.gov", "owasp.org", "acm.org", "ieee.org"]):
        return "A"
    if any(k in u for k in ["openai.com", "anthropic.com", "googleblog.com"]):
        return "B"
    return "C"


def _theme_tags(text: str, themes: list[str]) -> list[str]:
    lowered = text.lower()
    return [t for t in themes if t.replace("_", " ") in lowered or t in lowered]


def ingest_arxiv(sources_cfg: dict[str, Any], themes: list[str], run_date: date) -> list[dict[str, Any]]:
    if not sources_cfg.get("arxiv", {}).get("enabled", True):
        return []

    rows: list[dict[str, Any]] = []
    queries = sources_cfg.get("arxiv", {}).get("queries", [])
    max_results = int(sources_cfg.get("arxiv", {}).get("max_results_per_query", 25))

    for q in queries:
        url = f"{ARXIV_API}?search_query={quote_plus(q)}&start=0&max_results={max_results}"
        feed = feedparser.parse(url)
        for entry in feed.entries:
            summary = (entry.get("summary") or "").replace("\n", " ").strip()
            title = (entry.get("title") or "").replace("\n", " ").strip()
            published = (entry.get("published") or "")[:10]
            entry_id = entry.get("id", "")
            arxiv_id = entry_id.split("/")[-1] if entry_id else "unknown"
            text = f"{title} {summary}"
            rows.append(
                {
                    "id": f"source:arxiv:{arxiv_id}",
                    "title": title,
                    "summary": summary,
                    "url": entry.get("link", entry_id),
                    "published_at": published or iso_date(run_date),
                    "source_type": "arxiv",
                    "credibility_tier": "A",
                    "theme_tags": _theme_tags(text, themes),
                    "key_claims": [],
                    "why_it_matters": "",
                    "risk_notes": "",
                    "raw_text_snippets": [summary[:300]],
                }
            )
    return rows


def ingest_rss(sources_cfg: dict[str, Any], themes: list[str], run_date: date) -> list[dict[str, Any]]:
    if not sources_cfg.get("rss", {}).get("enabled", True):
        return []

    rows: list[dict[str, Any]] = []
    feeds = sources_cfg.get("rss", {}).get("feeds", [])
    for feed_url in feeds:
        parsed = feedparser.parse(feed_url)
        for entry in parsed.entries[:30]:
            title = (entry.get("title") or "").strip()
            summary = (entry.get("summary") or "").replace("\n", " ").strip()
            text = f"{title} {summary}"
            url = entry.get("link", feed_url)
            published = (entry.get("published") or entry.get("updated") or "")[:10]
            digest = str(abs(hash(f"{title}:{url}")))[:10]
            rows.append(
                {
                    "id": f"source:rss:{digest}",
                    "title": title,
                    "summary": summary,
                    "url": url,
                    "published_at": published or iso_date(run_date),
                    "source_type": "rss",
                    "credibility_tier": _credibility_from_url(url),
                    "theme_tags": _theme_tags(text, themes),
                    "key_claims": [],
                    "why_it_matters": "",
                    "risk_notes": "",
                    "raw_text_snippets": [summary[:300]],
                }
            )
    return rows


def ingest_standards(sources_cfg: dict[str, Any], themes: list[str], run_date: date) -> list[dict[str, Any]]:
    if not sources_cfg.get("standards", {}).get("enabled", True):
        return []

    rows: list[dict[str, Any]] = []
    for item in sources_cfg.get("standards", {}).get("items", []):
        title = item.get("title", "")
        url = item.get("url", "")
        text = f"{title} {url}"
        digest = str(abs(hash(f"{title}:{url}")))[:10]
        rows.append(
            {
                "id": f"source:standard:{digest}",
                "title": title,
                "summary": "Governance or security standard relevant to trustworthy deployment.",
                "url": url,
                "published_at": iso_date(run_date),
                "source_type": "standard",
                "credibility_tier": item.get("credibility_tier", "A"),
                "theme_tags": _theme_tags(text, themes),
                "key_claims": [],
                "why_it_matters": "",
                "risk_notes": "",
                "raw_text_snippets": [title],
            }
        )
    return rows


def run_ingest(
    raw_dir: str,
    run_date: date,
    sources_cfg: dict[str, Any],
    user_cfg: dict[str, Any],
) -> dict[str, str]:
    themes = user_cfg.get("themes", [])
    arxiv_rows = ingest_arxiv(sources_cfg, themes, run_date)
    rss_rows = ingest_rss(sources_cfg, themes, run_date)
    standards_rows = ingest_standards(sources_cfg, themes, run_date)

    arxiv_path = f"{raw_dir}/arxiv.jsonl"
    rss_path = f"{raw_dir}/rss.jsonl"
    standards_path = f"{raw_dir}/standards.jsonl"

    write_jsonl(path=Path(arxiv_path), rows=arxiv_rows)
    write_jsonl(path=Path(rss_path), rows=rss_rows)
    write_jsonl(path=Path(standards_path), rows=standards_rows)

    return {
        "arxiv": arxiv_path,
        "rss": rss_path,
        "standards": standards_path,
    }
