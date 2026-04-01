"""
Utility functions for Lagos Job Alert System
"""
import logging
import random
import time
import re
from datetime import datetime, timezone
from typing import Optional
import config

# ─── Logger Setup ─────────────────────────────────────────────────────────────
def setup_logger(name: str = "job_alert") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.LOG_LEVEL))
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    fh = logging.FileHandler(config.LOG_FILE)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger

logger = setup_logger()

# ─── Random User-Agent ────────────────────────────────────────────────────────
def get_random_headers() -> dict:
    return {
        "User-Agent": random.choice(config.USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

# ─── Retry Wrapper ────────────────────────────────────────────────────────────
def with_retry(func, *args, retries: int = config.MAX_RETRIES, **kwargs):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            logger.warning(f"Attempt {attempt}/{retries} failed: {e}")
            if attempt < retries:
                time.sleep(config.RETRY_DELAY * attempt)
    logger.error(f"All {retries} attempts failed. Last error: {last_error}")
    return None

# ─── Date Parsing ─────────────────────────────────────────────────────────────
RELATIVE_PATTERNS = {
    r"just now|moments? ago": 0,
    r"(\d+)\s*minute[s]?\s*ago": "minutes",
    r"(\d+)\s*hour[s]?\s*ago": "hours",
    r"(\d+)\s*day[s]?\s*ago": "days",
    r"yesterday": 1,
    r"today": 0,
}

ABSOLUTE_FORMATS = [
    "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y",
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y",
    "%d %b, %Y", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ",
]

def parse_date(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    raw = raw.strip()
    now = datetime.now(timezone.utc)

    for pattern, unit in RELATIVE_PATTERNS.items():
        match = re.search(pattern, raw, re.IGNORECASE)
        if match:
            from datetime import timedelta
            if unit == 0:
                return now
            elif unit == 1:
                return now.replace(hour=8, minute=0, second=0) - timedelta(days=1)
            else:
                n = int(match.group(1))
                if unit == "minutes":
                    return now - timedelta(minutes=n)
                elif unit == "hours":
                    return now - timedelta(hours=n)
                elif unit == "days":
                    return now - timedelta(days=n)

    raw_title = raw.strip().title()
    for fmt in ABSOLUTE_FORMATS:
        try:
            dt = datetime.strptime(raw_title, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass

    # Try ISO format with timezone offset directly
    try:
        from datetime import timedelta
        # Handle Z suffix
        iso = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        pass

    logger.debug(f"Could not parse date: '{raw}'")
    return None

def is_within_48_hours(dt: Optional[datetime]) -> bool:
    if dt is None:
        return False
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    return (now - dt) <= timedelta(hours=config.HOURS_LIMIT)

# ─── Location Helpers ────────────────────────────────────────────────────────
def normalize_location(location: str) -> str:
    return location.lower().strip()

def is_allowed_location(location: str) -> bool:
    """
    Returns True if location is in Lagos Island area.

    Logic:
    - If the location contains a specific EXCLUDED mainland area → always reject
    - If it contains a specific ALLOWED Island area → accept
    - If it's a vague Lagos string (e.g. "Lagos, Nigeria", "Lagos State") with
      no specific area → accept with benefit of the doubt (scraped from
      Lagos-Island-filtered search URLs so likely correct)
    - Anything else → reject
    """
    loc = normalize_location(location)

    # Hard reject: contains a known mainland area
    if any(area in loc for area in config.EXCLUDED_LOCATIONS):
        return False

    # Accept: contains a known Island area
    if any(area in loc for area in config.ALLOWED_LOCATIONS):
        return True

    # Accept vague "Lagos" entries — these come from Island-filtered search URLs
    # e.g. "Lagos, Nigeria" / "Lagos State" / "Lagos"
    vague_lagos = re.search(r"\blagos\b", loc)
    if vague_lagos:
        return True

    return False

# ─── Salary Normalizer ────────────────────────────────────────────────────────
def normalize_salary(raw: str) -> str:
    if not raw or raw.strip() in ("", "-", "N/A", "n/a", "None", "null"):
        return "Not Disclosed"
    raw = raw.strip()
    raw = re.sub(r"\bN\b", "₦", raw)
    raw = re.sub(r"\bNGN\b", "₦", raw, flags=re.IGNORECASE)
    return raw

# ─── URL Validator ────────────────────────────────────────────────────────────
def is_valid_url(url: str) -> bool:
    pattern = re.compile(
        r"^https?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
        r"localhost|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return bool(pattern.match(url or ""))

# ─── Deduplication ───────────────────────────────────────────────────────────
def job_fingerprint(job: dict) -> str:
    title = (job.get("title") or "").lower().strip()
    company = (job.get("company") or "").lower().strip()
    location = (job.get("location") or "").lower().strip()
    return f"{title}|{company}|{location}"

def deduplicate_jobs(jobs: list) -> list:
    seen = set()
    unique = []
    for job in jobs:
        key = job_fingerprint(job)
        if key not in seen:
            seen.add(key)
            unique.append(job)
    logger.info(f"Deduplication: {len(jobs)} → {len(unique)} jobs")
    return unique
