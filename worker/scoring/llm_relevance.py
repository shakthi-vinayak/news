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
OPENROUTER_MODEL    = os.getenv("OPENROUTER_MODEL",    "nvidia/nemotron-3-ultra-550b-a55b:free")

# Fallback chain: if the primary model is rate-limited, try these free models in order.
# Only free models are used -- paid models are never triggered.
FREE_MODEL_FALLBACKS = [
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openai/gpt-oss-120b:free",
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


MAX_RETRIES_PER_MODEL = 3
FALLBACK_RETRY_BASE_DELAY = 10  # seconds


def _chat_single(system: str, user_content: str, model: str) -> str:
    """Try a single model with retries. Returns response text or raises."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user",   "content": user_content},
        ],
        "max_tokens": 2048,
        "temperature": 0.1,
        # Prevent OpenRouter from falling back to paid models
        "provider": {
            "allow_fallbacks": False,
        },
    }
    for attempt in range(MAX_RETRIES_PER_MODEL):
        with _client() as client:
            resp = client.post("/chat/completions", json=payload)
            if resp.status_code == 429 or resp.status_code == 503:
                delay = FALLBACK_RETRY_BASE_DELAY * (2 ** attempt)
                log.warning(
                    "Model %s rate-limited (HTTP %d), retry %d/%d in %ds",
                    model, resp.status_code, attempt + 1, MAX_RETRIES_PER_MODEL, delay,
                )
                time.sleep(delay)
                continue
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"OpenRouter error with {model} (HTTP {resp.status_code}) -- will try next model"
                )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
    raise RuntimeError(f"Model {model} rate-limited after {MAX_RETRIES_PER_MODEL} retries")


def _chat(system: str, user_content: str, model: str) -> str:
    """Try the requested model, then fall back through free model chain."""
    # Build ordered list: requested model first, then remaining fallbacks
    models_to_try = [model]
    for m in FREE_MODEL_FALLBACKS:
        if m != model:
            models_to_try.append(m)

    last_err = None
    for m in models_to_try:
        try:
            result = _chat_single(system, user_content, m)
            if m != model:
                log.info("Succeeded with fallback model %s", m)
            return result
        except RuntimeError as exc:
            last_err = exc
            log.warning("Model %s failed: %s -- trying next free model", m, exc)

    raise RuntimeError(
        f"All free models exhausted (tried {', '.join(models_to_try)}). Last error: {last_err}"
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
    """
    if not OPENROUTER_API_KEY:
        log.warning("OPENROUTER_API_KEY not set — skipping LLM scoring for jobs")
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
