from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.common.io import write_json
from src.common.llm import LLMClient


def _contains_any(text: str, phrases: list[str]) -> bool:
    lowered = text.lower()
    return any(p.lower() in lowered for p in phrases)


def score_draft(
    draft_text: str,
    references: dict[str, Any],
    rubric_cfg: dict[str, Any],
    blacklist_phrases: list[str],
    history_texts: list[str],
) -> dict[str, Any]:
    t = draft_text.lower()

    systems = 3
    if _contains_any(t, ["systems implication", "incentive", "governance", "deployment"]):
        systems += 1
    if _contains_any(t, ["second-order", "failure mode", "constraints"]):
        systems += 1

    rigor = 3
    if _contains_any(t, ["technical anchor", "metric", "threat model", "evaluation"]):
        rigor += 1
    if _contains_any(t, ["boundary", "error bars", "assumption"]):
        rigor += 1

    clarity = 3
    lines = [ln for ln in draft_text.splitlines() if ln.strip()]
    if 8 <= len(lines) <= 20:
        clarity += 1
    if len(draft_text) < 2200:
        clarity += 1

    novelty = 4
    recent_joined = "\n".join(history_texts).lower()
    for marker in ["what evidence would change your deployment decision", "most teams are still optimizing"]:
        if marker in t and marker in recent_joined:
            novelty -= 1

    systems = min(5, systems)
    rigor = min(5, rigor)
    clarity = min(5, clarity)
    novelty = max(0, min(5, novelty))

    thresholds = rubric_cfg.get("thresholds", {})
    fails = []
    if systems < int(thresholds.get("systems_strategic", 4)):
        fails.append("systems_strategic_below_threshold")
    if rigor < int(thresholds.get("technical_rigor", 4)):
        fails.append("technical_rigor_below_threshold")

    if _contains_any(t, ["breakthrough", "revolutionary", "game-changer"]):
        fails.append("ungrounded_breakthrough_claim")
    if _contains_any(t, blacklist_phrases):
        fails.append("blacklist_phrase_detected")
    if not references.get("sources"):
        fails.append("missing_citations_for_factual_claims")

    return {
        "scores": {
            "systems_strategic": systems,
            "technical_rigor": rigor,
            "clarity": clarity,
            "novelty": novelty,
        },
        "passed": len(fails) == 0,
        "fail_reasons": fails,
    }


def revise_draft_once(draft_text: str, fail_reasons: list[str]) -> str:
    revised = draft_text
    if "systems_strategic_below_threshold" in fail_reasons and "Systems implication:" not in revised:
        revised += "\nSystems implication: incentives and governance structure determine whether technical gains translate safely.\n"
    if "technical_rigor_below_threshold" in fail_reasons and "Technical anchor:" not in revised:
        revised += "\nTechnical anchor: define the metric and threat model before claiming reliability improvements.\n"
    if "blacklist_phrase_detected" in fail_reasons:
        for phrase in ["game-changer", "revolutionary", "AI is changing everything"]:
            revised = revised.replace(phrase, "important")
            revised = revised.replace(phrase.title(), "Important")
    if "ungrounded_breakthrough_claim" in fail_reasons:
        revised = revised.replace("breakthrough", "incremental improvement")
    return revised


def score_draft_with_llm(
    draft_text: str,
    references: dict[str, Any],
    rubric_cfg: dict[str, Any],
    blacklist_phrases: list[str],
    history_texts: list[str],
    llm_client: LLMClient,
    model_cfg: dict[str, Any],
) -> dict[str, Any]:
    thresholds = rubric_cfg.get("thresholds", {})
    recent_post_summaries = []
    for text in history_texts[-10:]:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        recent_post_summaries.append(" ".join(lines[:3])[:320])

    system_prompt = """
You are a strict LinkedIn-post quality judge. Your job is to score a single draft post for a specific positioning goal:
- HIGH Systems & Strategic Thinking
- HIGH Technical Rigor
The author targets a senior, cross-industry audience.
You must be brutally honest, consistent, and conservative with high scores.
Do not reward hype, vagueness, or paper-summary-only content.

You MUST output valid JSON only matching the schema. No markdown. No commentary outside JSON.
""".strip()
    user_prompt = f"""
TASK
Score the draft on 0-5 integer dimensions: systems_strategic, technical_rigor, clarity, novelty.
Provide pass/fail decisions, actionable revisions, classifications, tracking fields, and concise observable-signal bullets.

RUBRIC HINTS (STRICT):
- systems_strategic 4+ requires structural/second-order/system-level reasoning.
- technical_rigor 4+ requires mechanism + constraint/failure mode.
- clarity rewards skimmable, high-signal writing.
- novelty should be conservative without RECENT context.

HARD GATES:
- has_technical_anchor
- has_systems_implication
- has_evaluative_judgment
- hype_or_vague
- ungrounded_factual_claims
- too_academic_summary
- too_influencer_style

PILLAR (pick one): insight_thinking | research_translation | field_reality | leadership_mentorship | personal_texture
HOOK TYPE (pick one): contrarian | framework | failure_story | translation | question | observation | announcement

INPUTS
<<<DRAFT
{draft_text}
DRAFT>>>
<<<SOURCES
{references}
SOURCES>>>
<<<RECENT
{recent_post_summaries}
RECENT>>>
BLACKLIST: {blacklist_phrases}

OUTPUT JSON SCHEMA:
{{
  "scores": {{
    "systems_strategic": 0,
    "technical_rigor": 0,
    "clarity": 0,
    "novelty": 0
  }},
  "hard_gates": {{
    "has_technical_anchor": false,
    "has_systems_implication": false,
    "has_evaluative_judgment": false,
    "hype_or_vague": false,
    "ungrounded_factual_claims": false,
    "too_academic_summary": false,
    "too_influencer_style": false
  }},
  "classification": {{
    "pillar": "",
    "hook_type": "",
    "themes": []
  }},
  "pass_fail": {{
    "thresholds": {{
      "systems_strategic_min": {int(thresholds.get("systems_strategic", 4))},
      "technical_rigor_min": {int(thresholds.get("technical_rigor", 4))},
      "clarity_min": {int(thresholds.get("clarity", 3))},
      "novelty_min": {int(thresholds.get("novelty", 3))}
    }},
    "passes": false,
    "reasons": []
  }},
  "revision_notes": {{
    "top_3_fixes": [],
    "line_edits": [],
    "missing_elements": []
  }},
  "tracking": {{
    "one_sentence_summary": "",
    "key_claims": [],
    "systems_implications": [],
    "technical_anchors": [],
    "repeated_phrases_candidates": []
  }},
  "reasoning_trace": []
}}
""".strip()
    raw = llm_client.chat_completion(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=float((model_cfg.get("temperature") or {}).get("evaluation", 0.1)),
        max_tokens=max(800, int((model_cfg.get("max_tokens") or {}).get("evaluation", 300))),
        response_format={"type": "json_object"},
    )
    parsed = json.loads(raw)
    scores = parsed.get("scores", {})
    normalized = {
        "systems_strategic": max(0, min(5, int(scores.get("systems_strategic", 0)))),
        "technical_rigor": max(0, min(5, int(scores.get("technical_rigor", 0)))),
        "clarity": max(0, min(5, int(scores.get("clarity", 0)))),
        "novelty": max(0, min(5, int(scores.get("novelty", 0)))),
    }
    pass_fail = parsed.get("pass_fail", {})
    fail_reasons = pass_fail.get("reasons", parsed.get("fail_reasons", []))
    if not isinstance(fail_reasons, list):
        fail_reasons = []
    passed = bool(pass_fail.get("passes", parsed.get("passed", False)))
    thresholds = rubric_cfg.get("thresholds", {})
    if normalized["systems_strategic"] < int(thresholds.get("systems_strategic", 4)):
        if "systems_strategic_below_threshold" not in fail_reasons:
            fail_reasons.append("systems_strategic_below_threshold")
        passed = False
    if normalized["technical_rigor"] < int(thresholds.get("technical_rigor", 4)):
        if "technical_rigor_below_threshold" not in fail_reasons:
            fail_reasons.append("technical_rigor_below_threshold")
        passed = False
    hard_gates = parsed.get("hard_gates", {})
    if bool(hard_gates.get("ungrounded_factual_claims")) and "missing_citations_for_factual_claims" not in fail_reasons:
        fail_reasons.append("missing_citations_for_factual_claims")
        passed = False
    return {
        "scores": normalized,
        "passed": passed,
        "fail_reasons": fail_reasons,
        "rationale": str(parsed.get("rationale", "")),
        "hard_gates": hard_gates if isinstance(hard_gates, dict) else {},
        "classification": parsed.get("classification", {}),
        "revision_notes": parsed.get("revision_notes", {}),
        "tracking": parsed.get("tracking", {}),
        "reasoning_trace": parsed.get("reasoning_trace", []),
    }


def revise_draft_with_llm(
    draft_text: str,
    fail_reasons: list[str],
    llm_client: LLMClient,
    model_cfg: dict[str, Any],
) -> str:
    system_prompt = "You revise technical posts with minimal edits. Return markdown only."
    user_prompt = f"""
Revise this draft to address fail reasons:
{fail_reasons}

Hard constraints:
- Keep same topic and tone.
- Include explicit technical anchor and systems implication.
- Keep concise and non-hype.
- Preserve section structure.

Draft:
{draft_text}
""".strip()
    return (
        llm_client.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=float((model_cfg.get("temperature") or {}).get("revision", 0.2)),
            max_tokens=int((model_cfg.get("max_tokens") or {}).get("revision", 700)),
        ).strip()
        + "\n"
    )


def quality_gate(
    draft_path: Path,
    references: dict[str, Any],
    rubric_cfg: dict[str, Any],
    blacklist_phrases: list[str],
    history_texts: list[str],
    llm_client: LLMClient | None = None,
    model_cfg: dict[str, Any] | None = None,
    max_revisions: int = 2,
) -> dict[str, Any]:
    draft_text = draft_path.read_text(encoding="utf-8")
    if llm_client is not None and model_cfg is not None:
        try:
            result = score_draft_with_llm(
                draft_text=draft_text,
                references=references,
                rubric_cfg=rubric_cfg,
                blacklist_phrases=blacklist_phrases,
                history_texts=history_texts,
                llm_client=llm_client,
                model_cfg=model_cfg,
            )
        except Exception:
            result = score_draft(draft_text, references, rubric_cfg, blacklist_phrases, history_texts)
    else:
        result = score_draft(draft_text, references, rubric_cfg, blacklist_phrases, history_texts)

    revision_count = 0
    while not result["passed"] and revision_count < max_revisions:
        if llm_client is not None and model_cfg is not None:
            try:
                draft_text = revise_draft_with_llm(
                    draft_text=draft_text,
                    fail_reasons=result["fail_reasons"],
                    llm_client=llm_client,
                    model_cfg=model_cfg,
                )
            except Exception:
                draft_text = revise_draft_once(draft_text, result["fail_reasons"])
        else:
            draft_text = revise_draft_once(draft_text, result["fail_reasons"])
        draft_path.write_text(draft_text, encoding="utf-8")
        if llm_client is not None and model_cfg is not None:
            try:
                result = score_draft_with_llm(
                    draft_text=draft_text,
                    references=references,
                    rubric_cfg=rubric_cfg,
                    blacklist_phrases=blacklist_phrases,
                    history_texts=history_texts,
                    llm_client=llm_client,
                    model_cfg=model_cfg,
                )
            except Exception:
                result = score_draft(draft_text, references, rubric_cfg, blacklist_phrases, history_texts)
        else:
            result = score_draft(draft_text, references, rubric_cfg, blacklist_phrases, history_texts)
        revision_count += 1

    result["revision_count"] = revision_count
    score_path = draft_path.with_name(draft_path.stem + "_score.json")
    write_json(score_path, result)
    result["score_path"] = str(score_path)
    return result
