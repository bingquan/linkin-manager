# spec.md — LinkedIn Manager Bot (Up-to-date, High-Rigor, Systems-Strategic)

## 0) One-liner
A repo-native “LinkedIn Manager Bot” that ingests weekly up-to-date sources, filters for user themes (e.g., AI agents, AI safety), generates a **next-week posting plan + drafts** that consistently signal **(a) high Systems & Strategic Thinking** and **(b) high Technical Rigor**, tracks what’s already posted, and updates the repo weekly via GitHub Actions.

---

## 1) Goals & Non-Goals

### Goals
1. **Up-to-date content pipeline**: weekly ingest of new sources (papers, blogs, standards, benchmarks, governance docs).
2. **Theme-driven**: user supplies themes + sub-themes + “stance constraints” (what to emphasize/avoid).
3. **Positioning consistency**: every draft must score high on:
   - Systems & Strategic Thinking
   - Depth of Technical Rigor
4. **Content allocation plan**: maintain pillar mix (e.g., Insight, Research translation, Field reality, Leadership) across weeks/months.
5. **Tracking**: maintain memory of what’s already posted (topics, claims, angles, repeated phrases).
6. **Weekly planning**: generate *next 7 days* worth of content (1–3 posts/week; default 2) with specific topics + sources.
7. **Repo outputs**:
   - a filtered “topics” folder (candidates and metadata)
   - a separate folder with actual post drafts + references/citations
8. **Model flexibility**: run with local **7B** or **heavily-quantized ~20B** model.

### Non-Goals
- Auto-posting to LinkedIn (out of scope; you’ll copy/paste drafts manually).
- Real-time streaming news (weekly batch is enough).
- Perfect fact verification (we’ll do citation + minimal cross-check, but not full journalistic verification).

---

## 2) User Experience (UX)

### Primary user input (config)
User edits `config/user_profile.yaml`:
- `themes`: list of themes (AI agents, AI safety, agent security, eval, governance)
- `audience`: (research leads, security engineers, policy, founders)
- `cadence`: posts/week (default 2)
- `pillars_allocation`: target distribution
- `tone`: direct, evaluative, non-hype
- `banned_moves`: (no generic motivation, no “paper summary only”, no hype claims without sources)

### Output artifacts per weekly run
1. `weekly/2026-W07/plan.md` — next week plan (topics, angles, hooks, CTA)
2. `weekly/2026-W07/drafts/post_01.md` — ready-to-post text
3. `weekly/2026-W07/drafts/post_01.references.json` — citations (URLs/DOIs/arXiv IDs), quote snippets if any
4. `topics/2026-W07/filtered_topics.jsonl` — ranked candidate topics + why
5. `state/content_log.jsonl` — append-only tracking of published/planned content
6. `state/coverage_dashboard.md` — coverage vs pillar mix, repetition alerts, theme drift warnings

---

## 3) System Architecture

### Modules
1. **Ingest**
   - Pull sources weekly from:
     - arXiv queries by theme keywords
     - RSS feeds (selected blogs/standards orgs)
     - curated governance/security sources (NIST, OWASP, etc. — configurable)
   - Output: `topics/RAW/<date>/*.jsonl`

2. **Filter & Rank**
   - Filter by theme relevance + freshness + credibility + novelty vs your history
   - Rank with composite score:
     - Relevance score (themes)
     - Novelty score (not repeating recent angles)
     - “Strategic leverage” score (systems-level implications)
     - Credibility score (source quality)
   - Output: `topics/<week>/filtered_topics.jsonl`

3. **Planner**
   - Convert top topics into a **7-day plan**:
     - assign to pillars based on allocation targets
     - ensure adjacency variety (avoid 2 “paper translation” posts in a row)
     - include at least 1 “systems critique” post/week
   - Output: `weekly/<week>/plan.md`

4. **Draft Generator**
   - Generate LinkedIn drafts with constraints:
     - hook + body + concrete claims + “what it implies” + question prompt
     - citations included in references file (not necessarily in post body)
   - Output: `weekly/<week>/drafts/*.md`

5. **Quality Gate (Scoring + lint)**
   - Score each draft on rubrics (0–5):
     - Systems & Strategic Thinking
     - Technical Rigor
     - Clarity & Brevity
     - Non-hype compliance
     - Novelty vs last N posts
   - If fails thresholds → revise loop (max 2 iterations)
   - Output: `weekly/<week>/drafts/*_score.json`

6. **Memory / Tracking**
   - Append content metadata:
     - theme tags, claims, repeated phrases, hook type, pillar
     - “topic saturation” counters (e.g., too much jailbreak talk)
   - Output: `state/content_log.jsonl`, `state/embeddings/` (optional)

---

## 4) Repo Structure

```text
linkedin-manager-bot/
  config/
    user_profile.yaml
    sources.yaml
    model.yaml
    rubric.yaml
  topics/
    RAW/
      2026-02-13/
        arxiv.jsonl
        rss.jsonl
        standards.jsonl
    2026-W07/
      filtered_topics.jsonl
      filter_report.md
  weekly/
    2026-W07/
      plan.md
      drafts/
        post_01.md
        post_01.references.json
        post_01_score.json
        post_02.md
        post_02.references.json
        post_02_score.json
  state/
    content_log.jsonl
    coverage_dashboard.md
    phrase_blacklist.txt
    topic_saturation.json
  src/
    ingest/
    rank/
    plan/
    draft/
    evaluate/
    memory/
  scripts/
    run_weekly.sh
    build_dashboard.py
  .github/
    workflows/
      weekly_update.yml
  README.md
  spec.md
```

---

## 5) Content Allocation Plan

Default pillars and targets (editable in `config/user_profile.yaml`):

* **Insight / Thinking**: 30%
* **Research Translation**: 25%
* **Field / Reality**: 25%
* **Leadership / Mentorship**: 15%
* **Personal Texture**: 5% (optional, capped)

Weekly enforcement:

* For 2 posts/week: pick 2 different pillars each week.
* For 3 posts/week: ensure at least 1 “systems critique” and 1 “technical translation.”

Anti-drift constraints:

* Max 1 “pure summary” post/month.
* Min 1 “evaluation critique” post/2 weeks.
* Avoid repeating the same paper venue/author cluster within 4 weeks unless major news.

---

## 6) Positioning Constraints (Hard Requirements)

Each draft MUST:

1. Include **one systems-level implication** (org, governance, deployment, incentives, evaluation failure surface).
2. Include **one technical anchor** (method detail, threat model, metric definition, limitation of evaluation).
3. Include **an evaluative judgment** (what’s missing, what will fail, what changes the conclusion).
4. Avoid:

   * empty hype (“game-changer”, “revolutionary”) unless backed by specific evidence
   * vague generalities (e.g., “AI is changing everything”)
   * influencer-style engagement bait without substance

Rubric targets (0–5):

* Systems & Strategic Thinking: **>= 4**
* Technical Rigor: **>= 4**
* Clarity: **>= 3**
* Novelty: **>= 3**

---

## 7) Data Model (Core Files)

### `topics/*.jsonl` record schema

```json
{
  "id": "source:arxiv:2602.08234",
  "title": "...",
  "summary": "...",
  "url": "...",
  "published_at": "2026-02-12",
  "source_type": "arxiv|rss|standard|blog",
  "credibility_tier": "A|B|C",
  "theme_tags": ["ai_agents", "ai_safety"],
  "key_claims": ["..."],
  "why_it_matters": "...",
  "risk_notes": "possible hype / unclear eval",
  "raw_text_snippets": ["..."]
}
```

### `state/content_log.jsonl` schema

```json
{
  "date": "2026-02-13",
  "week": "2026-W07",
  "status": "planned|published",
  "pillar": "insight|research_translation|field|leadership|personal",
  "themes": ["ai_agents","agent_security"],
  "topic_id": "source:arxiv:...",
  "hook_type": "contrarian|framework|failure_story|translation",
  "claims": ["..."],
  "repeated_phrase_flags": ["..."],
  "draft_path": "weekly/2026-W07/drafts/post_01.md"
}
```

---

## 8) Model & Runtime Requirements

### Supported model modes

1. **Local 7B** (fast, lower quality)
2. **Quantized ~20B** (slower, better judgment)

Config: `config/model.yaml`

* `backend`: `llama.cpp|vllm|ollama`
* `model_path`: local path
* `context_length`: default 8k (min)
* `temperature`: 0.4–0.7 (draft), 0.2 (revision), 0.0–0.2 (evaluation)
* `max_tokens`: per draft cap

Hardware assumptions:

* CPU-only possible (7B quant)
* GPU recommended for 20B even quantized

---

## 9) Pipeline Logic (Weekly)

### Weekly run steps

1. **Ingest** (fresh sources since last run)
2. **Filter** by:

   * freshness window (default 14 days)
   * theme match
   * credibility tier >= B (configurable)
3. **Rank** and select top K candidates (default 30)
4. **Plan** next week:

   * choose N posts = cadence
   * assign pillars to meet allocation targets
   * avoid repetition vs last 6–10 posts
5. **Draft** N posts:

   * include hook, technical anchor, systems implication, judgment
6. **Quality gate**:

   * score drafts
   * revise if below thresholds
7. **Write outputs** to `weekly/<week>/...`
8. **Update state** logs + dashboard

---

## 10) GitHub Actions (Weekly Update)

Workflow: `.github/workflows/weekly_update.yml`

* Trigger: weekly cron (e.g., Monday 08:00 Asia/Singapore)
* Steps:

  1. checkout repo
  2. setup python (or node) env
  3. run `scripts/run_weekly.sh`
  4. commit updated `topics/`, `weekly/`, `state/`
  5. open PR or push to main (configurable)

Important: GitHub Actions runners have constraints:

* If using a local model, you likely can’t run it on GitHub-hosted runners realistically.
* Two modes:

  * **Mode A (recommended):** Actions runs ingestion + filtering + planning skeleton; drafting runs locally.
  * **Mode B (self-hosted runner):** run full pipeline including LLM.

`config/model.yaml` should specify `runner_mode: hosted|self_hosted`.

---

## 11) Draft Format Standard (Post Markdown)

Each `post_XX.md` follows:

* **Hook** (1–2 lines)
* **Body** (4–10 short paragraphs)
* **Technical anchor** (one concrete detail)
* **Systems implication** (one paragraph)
* **Judgment / Recommendation** (1 paragraph)
* **Prompt question** (one line)

No links in body unless you explicitly want them. References go to JSON.

---

## 12) Reference File Standard

`post_XX.references.json` contains:

* sources with URLs
* identifiers (arXiv/DOI)
* 1–3 bullet “supporting evidence” snippets (short)
* confidence notes

Example:

```json
{
  "sources": [
    {"title": "...", "url": "...", "id": "arxiv:2602.08234"}
  ],
  "evidence": [
    {"source_id": "arxiv:2602.08234", "snippet": "Short excerpt...", "note": "supports claim X"}
  ],
  "confidence": "medium",
  "risk_flags": ["eval_unclear"]
}
```

---

## 13) Quality Gate (Rubrics)

### Systems & Strategic Thinking (0–5)

5 = identifies second-order effects, incentives, deployment constraints, governance implications.

### Technical Rigor (0–5)

5 = correct technical anchor, threat model/metric clarity, avoids overclaim.

### Novelty (0–5)

5 = clearly distinct from last N posts in angle + phrasing + examples.

### Clarity (0–5)

5 = concise, skimmable, no jargon pile-up.

Reject if:

* Systems < 4 OR Rigor < 4
* Contains ungrounded “breakthrough” claims
* No citations for factual claims

---

## 14) Safety & Compliance Notes

* Avoid sharing private/confidential data from your workplace/lab.
* Avoid naming students or internal incidents without permission.
* Keep claims falsifiable and sourced.

---

## 15) Implementation Milestones

### M1 — Skeleton Repo + Config + State

* folders, schemas, content_log, dashboard stub

### M2 — Ingest + Filter + Rank

* arXiv + RSS ingest, credibility tiers, theme tagger

### M3 — Weekly Planner

* pillar allocation engine + anti-repetition constraints

### M4 — Draft Generator + References

* post drafts + references JSON + revision loop

### M5 — GitHub Actions Integration

* hosted mode + self-hosted option

### M6 — Quality Gate + Dashboard

* scoring + repetition detector + coverage summary

---

## 16) Definition of Done

* Given themes in `user_profile.yaml`, the repo produces:

  * a ranked filtered topics file weekly
  * a next-week plan
  * N post drafts with references
  * updated state logs
* Drafts consistently pass rubric thresholds (Systems>=4, Rigor>=4).
* Weekly workflow runs via GitHub Actions (hosted planning; self-hosted full optional).

---

