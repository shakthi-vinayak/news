"""
worker/scoring/llm_relevance.py
OpenRouter-backed relevance scoring, summarisation, and tag assignment.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)

OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY  = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL    = os.getenv("OPENROUTER_MODEL",    "nvidia/nemotron-3-nano-30b-a3b:free")

# Free model pool — tried in parallel; first success wins.
# Ordered roughly by capability (best first). Only free models.
FREE_MODEL_POOL = [
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "google/gemma-4-31b-it:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "cohere/north-mini-code:free",
    "liquid/lfm-2.5-1.2b-instruct:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]

NEWS_TAGS = [
    "AI", "DevOps", "Kubernetes", "Cloud", "SRE", "Observability",
    "Platform Engineering", "Security", "Terraform", "CI/CD",
    "LLMOps", "MLOps", "Containers", "Service Mesh", "eBPF",
]

JOB_CATEGORIES = [
    "DevOps", "SRE", "Platform Engineering", "Observability",
    "Cloud Engineering", "Workflow Automation", "MLOps", "Security",
]

# Local keyword-based categorization (no AI required)
# Maps category names to keywords that should appear in job titles
CATEGORY_KEYWORDS = {
    "DevOps": ["devops", "dev ops", "ci/cd", "cicd", "jenkins", "gitlab", "github actions", "ansible", "terraform"],
    "SRE": ["sre", "site reliability", "reliability engineer", "production engineer"],
    "Platform Engineering": ["platform engineer", "platform engineering", "internal developer", "idp", "platform ops"],
    "Cloud Engineering": ["cloud engineer", "cloud engineering", "cloud operations", "aws", "gcp", "azure", "cloud infra"],
    "Observability": ["observability", "monitoring", "grafana", "prometheus", "datadog", "opentelemetry", "logging", "metrics"],
    "MLOps": ["mlops", "llmops", "ml engineer", "machine learning ops", "ai infrastructure", "ai platform"],
    "Security": ["security engineer", "devsecops", "security operations", "cloud security", "infrastructure security"],
    "Workflow Automation": ["workflow automation", "n8n", "airflow", "dagster", "prefect", "automation engineer"],
}

NEWS_SYSTEM = """\
You are a technical editor specialising in DevOps, SRE, Cloud, and AI/LLM infrastructure.
For each article provided, return a JSON array with one object per article in the same order.
Each object MUST have:
  "relevance_score": float 0.0-1.0 (relevance to DevOps/SRE/Cloud/AI/Platform Engineering)
  "summary": string (1-2 sentences, plain text, max 200 chars)
  "tags": array of strings chosen ONLY from: {tags}
Return ONLY the JSON array, no markdown fences, no commentary.
""".format(tags=NEWS_TAGS)

JOB_SYSTEM = """\
You are a technical recruiter specialising in DevOps, SRE, Cloud, and AI/LLM infrastructure.
For each job posting provided, return a JSON array with one object per posting in the same order.
Each object MUST have:
  "relevance_score": float 0.0-1.0 (relevance to DevOps/SRE/Cloud/AI Platform roles)
  "category": string chosen ONLY from: {cats}
Return ONLY the JSON array, no markdown fences, no commentary.
""".format(cats=JOB_CATEGORIES)


# ── HTTP client ──────────────────────────────────────────────────────────────
def _client() -> httpx.Client:
    return httpx.Client(
        base_url=OPENROUTER_BASE_URL,
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/devops-news-jobs-app",
        },
        timeout=60.0,
    )


MAX_RETRIES_PER_MODEL = 1  # keep low — parallel fan-out handles availability
RETRY_BASE_DELAY = 5  # seconds


def _make_payload(model: str, system: str, user_content: str) -> dict:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_content},
        ],
        "max_tokens": 2048,
        "temperature": 0.1,
        "provider": {
            "allow_fallbacks": False,
        },
    }


def _try_model(client: httpx.Client, model: str, payload: dict) -> tuple[str, str | None]:
    """Send one request. Returns (model, response_text) on success,
    or (model, None) on rate-limit/error."""
    try:
        resp = client.post("/chat/completions", json=payload)
        if resp.status_code in (429, 503):
            log.debug("Model %s rate-limited (HTTP %d)", model, resp.status_code)
            return (model, None)
        if resp.status_code >= 400:
            log.debug("Model %s error (HTTP %d)", model, resp.status_code)
            return (model, None)
        resp.raise_for_status()
        return (model, resp.json()["choices"][0]["message"]["content"].strip())
    except Exception as exc:
        log.debug("Model %s exception: %s", model, exc)
        return (model, None)


def _chat(system: str, user_content: str, model: str) -> str:
    """Fan-out to all free models in parallel; first success wins.
    Falls back to sequential retries if all fail in the first wave."""
    # Build model list: primary first, then the rest of the pool
    models = [model] + [m for m in FREE_MODEL_POOL if m != model]

    # ── Wave 1: parallel fan-out ────────────────────────────────────────
    with _client() as client:
        payloads = {m: _make_payload(m, system, user_content) for m in models}
        # Use httpx's connection pool to send all requests concurrently
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=len(models)) as pool:
            futures = {
                pool.submit(_try_model, client, m, payloads[m]): m
                for m in models
            }
            for future in as_completed(futures):
                m, text = future.result()
                if text is not None:
                    if m != model:
                        log.info("Primary model unavailable, used %s instead", m)
                    else:
                        log.debug("Succeeded with primary model %s", m)
                    # Cancel remaining futures
                    for f in futures:
                        f.cancel()
                    return text

    # ── Wave 2: sequential retry with backoff ───────────────────────────
    log.warning("All models rate-limited in parallel wave, retrying sequentially...")
    for attempt in range(MAX_RETRIES_PER_MODEL):
        for m in models:
            try:
                with _client() as client:
                    payload = _make_payload(m, system, user_content)
                    resp = client.post("/chat/completions", json=payload)
                    if resp.status_code in (429, 503):
                        continue
                    if resp.status_code >= 400:
                        continue
                    resp.raise_for_status()
                    text = resp.json()["choices"][0]["message"]["content"].strip()
                    log.info("Succeeded with %s on sequential retry (attempt %d)", m, attempt + 1)
                    return text
            except Exception:
                continue
        delay = RETRY_BASE_DELAY * (2 ** attempt)
        log.warning("All models still rate-limited, waiting %ds before retry...", delay)
        time.sleep(delay)

    raise RuntimeError(
        f"All free models exhausted after parallel + sequential retries "
        f"(tried {', '.join(models)})"
    )


def _safe_parse(raw: str) -> list[dict]:
    """Parse JSON array from LLM response, stripping markdown fences if present."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # strip opening fence
        lines = lines[1:] if lines[0].startswith("```") else lines
        # strip closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return json.loads(text)


# ── Public API ───────────────────────────────────────────────────────────────
def categorize_job_locally(item: dict[str, Any]) -> str:
    """
    Assign a category to a job based on keyword matching in title.
    This works without AI and ensures jobs always have categories.
    """
    title = (item.get("title") or "").lower()
    
    # Score each category by how many keywords match
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in title)
        if score > 0:
            scores[category] = score
    
    if not scores:
        return ""  # No match found
    
    # Return the category with highest score
    return max(scores, key=scores.get)


def score_news_batch(
    items: list[dict[str, Any]],
    *,
    model: str | None = None,
    batch_size: int = 10,
) -> list[dict[str, Any]]:
    """
    Score a list of news items in batches.
    Returns the same list with 'relevance_score', 'summary', and 'tags' populated.
    """
    if not OPENROUTER_API_KEY:
        log.warning("OPENROUTER_API_KEY not set — skipping LLM scoring for news")
        return items

    model = model or OPENROUTER_MODEL
    out: list[dict] = []

    for i in range(0, len(items), batch_size):
        batch = items[i: i + batch_size]
        user_payload = json.dumps([
            {"index": j, "title": item.get("title", ""), "url": item.get("url", "")}
            for j, item in enumerate(batch)
        ])
        try:
            raw = _chat(NEWS_SYSTEM, user_payload, model)
            results = _safe_parse(raw)
            for j, item in enumerate(batch):
                merged = {**item}
                if j < len(results):
                    r = results[j]
                    merged["relevance_score"] = float(r.get("relevance_score", 0))
                    merged["summary"]         = r.get("summary") or item.get("summary", "")
                    merged["tags"]            = r.get("tags") or item.get("tags", [])
                out.append(merged)
        except Exception as exc:
            log.error("LLM news batch %d failed: %s", i // batch_size, exc)
            out.extend(batch)  # keep unscored items rather than dropping them

    return out


def score_jobs_batch(
    items: list[dict[str, Any]],
    *,
    model: str | None = None,
    batch_size: int = 10,
) -> list[dict[str, Any]]:
    """
    Score a list of job items in batches.
    Returns the same list with 'relevance_score' and 'category' populated.
    
    Strategy:
    1. Always apply local categorization first (no AI required)
    2. Then try LLM scoring if API key is available (can improve categories)
    """
    # Step 1: Always apply local categorization first
    for item in items:
        if not item.get("category"):  # Only if not already set
            item["category"] = categorize_job_locally(item)
    
    if not OPENROUTER_API_KEY:
        log.info("OPENROUTER_API_KEY not set — using local keyword-based categorization")
        return items

    model = model or OPENROUTER_MODEL
    out: list[dict] = []

    for i in range(0, len(items), batch_size):
        batch = items[i: i + batch_size]
        user_payload = json.dumps([
            {
                "index": j,
                "title":   item.get("title", ""),
                "company": item.get("company", ""),
            }
            for j, item in enumerate(batch)
        ])
        try:
            raw = _chat(JOB_SYSTEM, user_payload, model)
            results = _safe_parse(raw)
            for j, item in enumerate(batch):
                merged = {**item}
                if j < len(results):
                    r = results[j]
                    merged["relevance_score"] = float(r.get("relevance_score", 0))
                    merged["category"]        = r.get("category") or item.get("category", "")
                out.append(merged)
        except Exception as exc:
            log.error("LLM jobs batch %d failed: %s", i // batch_size, exc)
            out.extend(batch)

    return out
