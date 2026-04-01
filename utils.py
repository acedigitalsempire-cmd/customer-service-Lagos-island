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

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler
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
    "%B %d, %Y",     # January 15, 2025
    "%b %d, %Y",     # Jan 15, 2025
    "%d %B %Y",      # 15 January 2025
    "%d %b %Y",      # 15 Jan 2025
    "%Y-%m-%d",      # 2025-01-15
    "%d/%m/%Y",      # 15/01/2025
    "%m/%d/%Y",      # 01/15/2025
    "%d-%m-%Y",      # 15-01-2025
    "%d %b, %Y",     # 15 Jan, 2025
]


def parse_date(raw: str) -> Optional[datetime]:
    """Parse a raw date string into a timezone-aware datetime (UTC)."""
    if not raw:
        return None

    raw = raw.strip().lower()
    now = datetime.now(timezone.utc)

    # Relative: "X minutes/hours/days ago"
    for pattern, unit in RELATIVE_PATTERNS.items():
        match = re.search(pattern, raw, re.IGNORECASE)
        if match:
            if unit == 0:
                return now
            elif unit == 1:  # yesterday
                from datetime import timedelta
                return now.replace(hour=8, minute=0, second=0) - timedelta(days=1)
            else:
                from datetime import timedelta
                n = int(match.group(1))
                if unit == "minutes":
                    return now - timedelta(minutes=n)
                elif unit == "hours":
                    return now - timedelta(hours=n)
                elif unit == "days":
                    return now - timedelta(days=n)

    # Absolute date formats
    raw_title = raw.strip().title()
    for fmt in ABSOLUTE_FORMATS:
        try:
            dt = datetime.strptime(raw_title, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    logger.debug(f"Could not parse date: '{raw}'")
    return None


def is_within_48_hours(dt: Optional[datetime]) -> bool:
    """Return True if dt is within the last 48 hours."""
    if dt is None:
        return False
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    return (now - dt) <= timedelta(hours=config.HOURS_LIMIT)


# ─── Location Helpers ────────────────────────────────────────────────────────
def normalize_location(location: str) -> str:
    return location.lower().strip()


def is_allowed_location(location: str) -> bool:
    loc = normalize_location(location)
    # Must match an allowed area
    allowed = any(area in loc for area in config.ALLOWED_LOCATIONS)
    # Must NOT match an excluded area
    excluded = any(area in loc for area in config.EXCLUDED_LOCATIONS)
    return allowed and not excluded


# ─── Salary Normalizer ────────────────────────────────────────────────────────
def normalize_salary(raw: str) -> str:
    if not raw or raw.strip() in ("", "-", "N/A", "n/a", "None", "null"):
        return "Not Disclosed"
    raw = raw.strip()
    # Ensure ₦ symbol
    raw = re.sub(r"\bN\b", "₦", raw)
    raw = re.sub(r"\bNGN\b", "₦", raw, flags=re.IGNORECASE)
    return raw


# ─── URL Validator ────────────────────────────────────────────────────────────
def is_valid_url(url: str) -> bool:
    pattern = re.compile(
        r"^https?://"
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
        r"localhost|"
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        r"(?::\d+)?"
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )
    return bool(pattern.match(url or ""))


# ─── Deduplication Key ───────────────────────────────────────────────────────
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
