"""
Filter module — applies all strict criteria to raw job listings.
"""
from typing import List, Dict, Optional
from utils import (
    logger, parse_date, is_within_48_hours,
    is_allowed_location, normalize_salary, is_valid_url, deduplicate_jobs,
)


def filter_jobs(raw_jobs: List[Dict]) -> List[Dict]:
    """
    Apply all filters:
      1. Location must be Lagos Island area (not mainland)
      2. Date posted must be within 48 hours (skip if no date)
      3. Salary normalised (Not Disclosed if missing)
      4. Link must be valid
      5. Deduplicate
    Returns cleaned, sorted list (newest first).
    """
    passed = []
    stats = {
        "total": len(raw_jobs),
        "no_date": 0,
        "too_old": 0,
        "wrong_location": 0,
        "bad_link": 0,
        "passed": 0,
    }

    for job in raw_jobs:
        title = (job.get("title") or "").strip()
        if not title:
            continue

        # ── 1. Date filter ──────────────────────────────────────────────────
        raw_date = job.get("date_posted", "")
        parsed_dt = parse_date(raw_date)

        if parsed_dt is None:
            stats["no_date"] += 1
            logger.debug(f"SKIP (no date): {title}")
            continue

        if not is_within_48_hours(parsed_dt):
            stats["too_old"] += 1
            logger.debug(f"SKIP (too old — {raw_date}): {title}")
            continue

        # ── 2. Location filter ──────────────────────────────────────────────
        location = job.get("location", "")
        if not is_allowed_location(location):
            stats["wrong_location"] += 1
            logger.debug(f"SKIP (location '{location}'): {title}")
            continue

        # ── 3. Link validation ──────────────────────────────────────────────
        link = job.get("link", "")
        if not is_valid_url(link):
            stats["bad_link"] += 1
            logger.debug(f"SKIP (bad link): {title}")
            continue

        # ── 4. Normalise fields ─────────────────────────────────────────────
        job["salary"] = normalize_salary(job.get("salary", ""))
        job["date_obj"] = parsed_dt
        job["date_display"] = parsed_dt.strftime("%d %b %Y %H:%M UTC")
        job["deadline"] = (job.get("deadline") or "Not Specified").strip() or "Not Specified"

        # Tag high-paying jobs (salary contains large numbers)
        import re
        salary_str = job["salary"]
        amounts = re.findall(r"[\d,]+", salary_str.replace(",", ""))
        job["high_paying"] = any(int(a) >= 200000 for a in amounts if a.isdigit() and len(a) >= 6)

        stats["passed"] += 1
        passed.append(job)

    logger.info(
        f"Filter summary → total={stats['total']} | "
        f"no_date={stats['no_date']} | too_old={stats['too_old']} | "
        f"wrong_location={stats['wrong_location']} | bad_link={stats['bad_link']} | "
        f"passed={stats['passed']}"
    )

    # Deduplicate
    passed = deduplicate_jobs(passed)

    # Sort newest first
    passed.sort(key=lambda j: j["date_obj"], reverse=True)

    return passed
