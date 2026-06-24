"""
collectors/jobs/jobsurface.py
Scrapes job listings from Job Surface (jobsurface.com).
Job Surface is a beehiiv newsletter that posts weekly DevOps & Cloud jobs.
It embeds listings as HTML in each post page.
We scrape the latest post (found via sitemap.xml) and parse job entries.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

from scoring.dedupe import make_job_id

log = logging.getLogger(__name__)

SITEMAP_URL = "https://www.jobsurface.com/sitemap.xml"
BASE_URL = "https://www.jobsurface.com"
SOURCE_NAME = "Job Surface"


def _get_latest_post_url() -> str | None:
    """Fetch sitemap.xml and return the URL of the latest /p/devops-jobs-* post."""
    try:
        resp = requests.get(SITEMAP_URL, timeout=15)
        resp.raise_for_status()
        # Parse URLs matching the post pattern
        pattern = re.compile(r"https://www\.jobsurface\.com/p/devops-jobs-\d+")
        urls = pattern.findall(resp.text)
        if not urls:
            log.warning("No Job Surface post URLs found in sitemap")
            return None
        # Sitemap is usually ordered newest-first, but sort by URL number to be safe
        def _sort_key(url: str) -> int:
            m = re.search(r"devops-jobs-(\d+)", url)
            return int(m.group(1)) if m else 0
        urls.sort(key=_sort_key, reverse=True)
        return urls[0]
    except Exception as exc:
        log.error("Failed to fetch Job Surface sitemap: %s", exc)
        return None


def _parse_post_jobs(html: str, max_items: int = 200) -> list[dict]:
    """Parse job listings from a Job Surface post page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    collected: list[dict] = []

    # Job Surface uses list items like:
    # "Company is hiring a Title Location: Location"
    # We look for <li> or text patterns matching this format
    # Also handles: "Company is hiring a Title Remote Location: Location"

    # Strategy: find all <li> elements and match the hiring pattern
    job_pattern = re.compile(
        r"(.+?)\s+is\s+hiring\s+(?:a\s+|an\s+)?(.+?)(?:\s+Remote\s+Location:\s+(.+))?$",
        re.IGNORECASE,
    )

    for li in soup.find_all("li"):
        text = li.get_text(strip=True)
        if not text:
            continue

        m = job_pattern.match(text)
        if not m:
            continue

        company = m.group(1).strip()
        title = m.group(2).strip()
        location = (m.group(3) or "Remote").strip()

        # Find the apply link (first <a> inside the <li>)
        apply_url = ""
        a_tag = li.find("a", href=True)
        if a_tag:
            apply_url = a_tag["href"]

        if not title or not company:
            continue

        item_id = make_job_id(apply_url or f"{company}|{title}", title, company, SOURCE_NAME)

        collected.append({
            "id":              item_id,
            "title":           title,
            "company":         company,
            "url":             apply_url or "",
            "source":          SOURCE_NAME,
            "location":        location,
            "posted_at":       datetime.now(timezone.utc).isoformat(),
            "category":        "",
            "relevance_score": 0.0,
            "salary_range":    None,
        })

        if len(collected) >= max_items:
            break

    return collected


def collect(cfg: dict[str, Any]) -> list[dict]:
    """
    cfg keys (from config.yaml jobs.jobsurface):
      max_items     -- cap on number of jobs to collect
    """
    max_items = cfg.get("max_items", 200)

    # Step 1: Find the latest post URL
    post_url = _get_latest_post_url()
    if not post_url:
        log.warning("Job Surface: no post URL found, skipping")
        return []

    log.info("Job Surface: fetching latest post %s", post_url)

    # Step 2: Fetch and parse the post
    try:
        resp = requests.get(post_url, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        log.error("Job Surface: failed to fetch post: %s", exc)
        return []

    jobs = _parse_post_jobs(resp.text, max_items=max_items)

    # If HTML parsing didn't find structured listings, try the Airtable link
    if not jobs:
        airtable_pattern = re.compile(r"https://airtable\.com/\S+")
        m = airtable_pattern.search(resp.text)
        if m:
            log.info("Job Surface: found Airtable link %s (cannot scrape directly)", m.group(0))

    log.info("Job Surface: collected %d jobs from %s", len(jobs), post_url)
    return jobs