from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.common.io import write_json
from src.common.llm import LLMClient


def _first_claim(topic: dict[str, Any]) -> str:
    claims = topic.get("key_claims") or []
    if claims:
        return claims[0]
    return "The public narrative overstates capability when evaluation scope is narrow."


def _technical_anchor(topic: dict[str, Any]) -> str:
    summary = (topic.get("summary") or "").lower()
    if "benchmark" in summary or "eval" in summary:
        return "Technical anchor: benchmark choice and metric definition can hide failure transfer to real tasks."
    if "security" in summary or "threat" in summary:
        return "Technical anchor: threat model assumptions define whether the reported mitigation is meaningful."
    return "Technical anchor: claims should map to explicit metrics, boundary conditions, and error bars."


def _systems_implication(topic: dict[str, Any]) -> str:
    return (
        "Systems implication: organizations that separate model quality from governance quality "
        "will misprice operational risk, especially when incentives reward launch speed over eval depth."
    )


def _judgment(topic: dict[str, Any]) -> str:
    return (
        "Judgment: this is useful progress, but teams should delay broad rollout until they can reproduce "
        "results under their own threat model and monitoring constraints."
    )


def generate_draft(
    post_spec: dict[str, Any],
    topic: dict[str, Any],
    tone: list[str],
    llm_client: LLMClient | None = None,
    model_cfg: dict[str, Any] | None = None,
) -> str:
    if llm_client is not None and model_cfg is not None:
        try:
            return _generate_draft_llm(post_spec, topic, tone, llm_client, model_cfg)
        except Exception:
            pass

    hook = post_spec["hook"]
    title = topic.get("title", "Topic")
    claim = _first_claim(topic)
    anchor = _technical_anchor(topic)
    systems = _systems_implication(topic)
    judgment = _judgment(topic)

    body = [
        hook,
        "",
        f"{title} is worth attention, but only if we separate signal from framing.",
        f"Core claim: {claim}",
        "",
        "Most discussion focuses on first-order performance metrics.",
        "The practical question is what fails when assumptions shift: data regime, user behavior, and adversarial pressure.",
        "",
        anchor,
        "",
        systems,
        "",
        judgment,
        "",
        "Prompt question: What evidence would change your deployment decision this quarter?",
    ]
    return "\n".join(body).strip() + "\n"


def generate_references(
    topic: dict[str, Any],
    llm_client: LLMClient | None = None,
    model_cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if llm_client is not None and model_cfg is not None:
        try:
            return _generate_references_llm(topic, llm_client, model_cfg)
        except Exception:
            pass

    topic_id = topic.get("id", "unknown")
    source = {
        "title": topic.get("title", ""),
        "url": topic.get("url", ""),
        "id": topic_id.replace("source:", "", 1),
    }
    snippet = (topic.get("summary") or "").strip()
    if len(snippet) > 220:
        snippet = snippet[:220].rstrip() + "..."

    return {
        "sources": [source],
        "evidence": [
            {
                "source_id": source["id"],
                "snippet": snippet,
                "note": "supports the post's central claim",
            }
        ],
        "confidence": "medium",
        "risk_flags": ["eval_unclear"] if "eval" in snippet.lower() else [],
    }


def _generate_draft_llm(
    post_spec: dict[str, Any],
    topic: dict[str, Any],
    tone: list[str],
    llm_client: LLMClient,
    model_cfg: dict[str, Any],
) -> str:
    system_prompt = (
        "You write high-rigor LinkedIn posts for senior technical audiences. "
        "Avoid hype. Include concrete, falsifiable claims."
    )
    user_prompt = f"""
Write one LinkedIn post in markdown using this exact section order:
1) Hook (1-2 lines)
2) Body (4-10 short paragraphs)
3) Technical anchor (one concrete detail)
4) Systems implication (one paragraph)
5) Judgment / Recommendation (one paragraph)
6) Prompt question (one line)

Hard constraints:
- Include one systems-level implication.
- Include one technical anchor (method, threat model, metric, or eval limitation).
- Include one evaluative judgment.
- No empty hype or influencer bait.
- Tone: {", ".join(tone)}

Plan context:
- Pillar: {post_spec.get("pillar")}
- Angle: {post_spec.get("angle")}
- Hook seed: {post_spec.get("hook")}

Topic:
- Title: {topic.get("title")}
- Summary: {topic.get("summary")}
- URL: {topic.get("url")}
- Theme tags: {topic.get("theme_tags")}
""".strip()
    out = llm_client.chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=float((model_cfg.get("temperature") or {}).get("draft", 0.5)),
        max_tokens=int((model_cfg.get("max_tokens") or {}).get("draft", 900)),
    )
    return out.strip() + "\n"


def _generate_references_llm(topic: dict[str, Any], llm_client: LLMClient, model_cfg: dict[str, Any]) -> dict[str, Any]:
    system_prompt = "Return strict JSON only."
    user_prompt = f"""
Produce references JSON with schema:
{{
  "sources": [{{"title":"...","url":"...","id":"..."}}],
  "evidence": [{{"source_id":"...","snippet":"...","note":"..."}}],
  "confidence": "low|medium|high",
  "risk_flags": ["..."]
}}

Use only this topic data:
- id: {topic.get("id")}
- title: {topic.get("title")}
- summary: {topic.get("summary")}
- url: {topic.get("url")}
""".strip()
    out = llm_client.chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=float((model_cfg.get("temperature") or {}).get("evaluation", 0.1)),
        max_tokens=int((model_cfg.get("max_tokens") or {}).get("evaluation", 300)),
        response_format={"type": "json_object"},
    )
    parsed = json.loads(out)
    return {
        "sources": parsed.get("sources", []),
        "evidence": parsed.get("evidence", []),
        "confidence": parsed.get("confidence", "medium"),
        "risk_flags": parsed.get("risk_flags", []),
    }


def write_draft_bundle(
    out_dir: Path,
    post_index: int,
    draft_text: str,
    references: dict[str, Any],
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    draft_path = out_dir / f"post_{post_index:02d}.md"
    ref_path = out_dir / f"post_{post_index:02d}.references.json"

    draft_path.write_text(draft_text, encoding="utf-8")
    write_json(ref_path, references)

    return draft_path, ref_path
