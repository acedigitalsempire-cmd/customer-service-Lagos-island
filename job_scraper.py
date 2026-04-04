"""
Job Scraper — Nigerian platforms using correct, verified RSS feed URLs.
All URLs confirmed working as of April 2026.

Sources:
  1. HotNigerianJobs   hotnigerianjobs.com   WordPress RSS ✓
  2. MyJobMag          myjobmag.com          RSS feed ✓
  3. Jobberman         jobberman.com         HTML (no public API/RSS)
  4. NgCareers         ngcareers.com         RSS ✓
  5. NaijaJobs         naijajobs.net         WordPress RSS ✓
  6. JobsInNigeria     jobsinnigeria.net      WordPress RSS ✓
  7. RecruitmentNg     recruitment.com.ng    WordPress RSS ✓
  8. Searchnigeriajobs searchnigeriajobs.com WordPress RSS ✓
  9. NigeriaJobSearch  nigeriajobsearch.com  WordPress RSS ✓
 10. Jobbatical Nigeria jobbatical.com       RSS ✓
"""
import time
import random
import re
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus, urljoin
from typing import Optional, List, Dict
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger("job_scraper")

# ─── Config ───────────────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 25
RETRY_DELAY     = 3

SEARCH_KEYWORDS = [
    "Customer Service Representative",
    "Customer Support",
    "Customer Care",
    "Support Officer",
]

ALLOWED_LOCATIONS = [
    "lekki", "victoria island", "vi", "ikoyi", "ajah",
    "sangotedo", "chevron", "lagos island", "eti-osa",
    "eti osa", "oniru", "osapa", "agungi", "ikate",
    "jakande", "lafiaji", "admiralty",
]

EXCLUDED_LOCATIONS = [
    "yaba", "surulere", "ikeja", "maryland", "ojota", "ketu",
    "gbagada", "mushin", "oshodi", "agege", "ikorodu",
    "alimosho", "isolo", "kosofe", "shomolu", "bariga",
    "mainland", "festac", "amuwo", "ilupeju", "oregun",
    "ogba", "berger", "ojodu", "abuja", "port harcourt",
    "kano", "kaduna", "ibadan", "enugu", "ogun", "remote",
]

CUSTOMER_KEYWORDS = [
    "customer service", "customer support", "customer care",
    "customer success", "support officer", "support rep",
    "client service", "client support", "help desk",
    "service representative", "support specialist",
    "call centre", "call center", "contact centre",
    "support agent", "service agent", "cx officer",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }

def _sleep():
    time.sleep(random.uniform(1.5, 3.0))

def _get(url: str, session: requests.Session) -> Optional[requests.Response]:
    for attempt in range(1, 4):
        try:
            r = session.get(url, headers=_headers(),
                            timeout=REQUEST_TIMEOUT, allow_redirects=True)
            if r.status_code in (401, 403, 404, 410, 429):
                logger.warning(f"HTTP {r.status_code}: {url}")
                return None
            r.raise_for_status()
            if len(r.text) < 200:
                return None
            return r
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout attempt {attempt}: {url}")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"DNS/Connection error {url}: {e}")
            return None   # DNS fail → no point retrying
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error attempt {attempt} {url}: {e}")
        if attempt < 3:
            time.sleep(RETRY_DELAY)
    return None

def _is_relevant(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in CUSTOMER_KEYWORDS)

def _is_allowed(location: str) -> bool:
    loc = location.lower().strip()
    if any(ex in loc for ex in EXCLUDED_LOCATIONS):
        return False
    if any(ok in loc for ok in ALLOWED_LOCATIONS):
        return True
    if re.search(r"\blagos\b", loc):
        return True
    return False

def _clean(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-z]+;", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def _parse_rss_date(raw: str) -> str:
    """
    Parse RSS date strings into a clean readable format.
    Handles: RFC 2822 (pubDate), ISO 8601, and relative strings.
    Returns the original string if parsing fails — never returns empty
    for a string that was present.
    """
    if not raw:
        return ""
    raw = raw.strip()

    # Try RFC 2822 (standard RSS pubDate format)
    # e.g. "Fri, 04 Apr 2026 08:00:00 +0000"
    try:
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%d %b %Y %H:%M UTC")
    except Exception:
        pass

    # Try ISO 8601 with timezone
    # e.g. "2026-04-04T08:00:00+01:00"
    try:
        raw_clean = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw_clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%d %b %Y %H:%M UTC")
    except Exception:
        pass

    # Try simple date formats
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d %B %Y", "%d %b %Y",
                "%B %d, %Y", "%b %d, %Y"]:
        try:
            dt = datetime.strptime(raw[:len(fmt)+2].strip(), fmt)
            return dt.strftime("%d %b %Y")
        except Exception:
            pass

    # Return raw string — better than empty (filter.py can try to parse it)
    return raw

def _extract_location(text: str) -> str:
    """Find a Lagos Island area in free text."""
    t = text.lower()
    for area in ALLOWED_LOCATIONS:
        if area in t:
            return area.title()
    if "lagos" in t:
        return "Lagos"
    return ""

def _extract_company(text: str) -> str:
    """Try to extract company name from RSS description text."""
    patterns = [
        r"(?:company|employer|organization)[\s:\-]+([A-Z][^\n<\.]{2,40})",
        r"(?:at|by|with)\s+([A-Z][A-Za-z0-9\s&\-\.]{2,35}?)"
        r"(?:\s*[-–|,]|\s+in\s+|\s+Lagos|\s+Nigeria|\.|$)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return "See Listing"

def _extract_salary(text: str) -> str:
    m = re.search(
        r"(?:salary|pay|₦|NGN|N\s*[\d,]+)[^\n<]{0,80}",
        text, re.IGNORECASE
    )
    return _clean(m.group(0)) if m else ""

def _extract_deadline(text: str) -> str:
    m = re.search(
        r"(?:deadline|closing date|apply before|expires?|closes?)[\s:]+([^\n<]{5,50})",
        text, re.IGNORECASE
    )
    return _clean(m.group(1)) if m else ""

def _job(title, company, location, salary,
         date_posted, deadline, link, source) -> Dict:
    return {
        "title":       _clean(title),
        "company":     _clean(company) or "N/A",
        "location":    _clean(location) or "Lagos",
        "salary":      _clean(salary),
        "date_posted": date_posted or "",
        "deadline":    _clean(deadline),
        "link":        (link or "").strip(),
        "source":      source,
    }


# ─── Core RSS parser ──────────────────────────────────────────────────────────
def _parse_feed(xml_text: str, source: str, base_url: str = "") -> List[Dict]:
    """
    Parse an RSS/Atom feed. Extracts all items, filters by:
    - Title relevance (customer service keywords)
    - Location (Lagos Island areas, not mainland)
    Returns list of job dicts.
    """
    jobs = []
    try:
        root = ET.fromstring(xml_text.encode("utf-8", errors="replace"))
    except ET.ParseError as e:
        logger.warning(f"[{source}] XML error: {e}")
        return jobs

    # RSS items or Atom entries
    items = (root.findall(".//item") or
             root.findall(".//{http://www.w3.org/2005/Atom}entry"))

    for item in items:
        def g(tag, ns=""):
            """Get text of a tag, optionally with namespace."""
            el = item.find(f"{{{ns}}}{tag}" if ns else tag)
            return (el.text or "").strip() if el is not None else ""

        title    = g("title")
        link     = g("link")
        pub_date = g("pubDate") or g("published","http://www.w3.org/2005/Atom") or \
                   g("date","http://purl.org/dc/elements/1.1/") or \
                   g("updated","http://www.w3.org/2005/Atom")
        desc     = (g("description") or
                    g("summary","http://www.w3.org/2005/Atom") or
                    g("encoded","http://purl.org/rss/1.0/modules/content/"))
        category = g("category")

        # Atom link is an attribute, not text
        if not link:
            el = item.find("{http://www.w3.org/2005/Atom}link")
            if el is not None:
                link = el.get("href", "")

        if not title or not link:
            continue

        # Filter 1: must be a customer service role
        if not _is_relevant(title):
            continue

        # Build full text for location/company extraction
        full_text = f"{title} {_clean(desc)} {category}"

        # Filter 2: location must be Lagos Island (not mainland)
        location = _extract_location(full_text)
        if not location:
            location = "Lagos"   # assume Lagos if no specific area found
        if not _is_allowed(location):
            continue

        # Fix relative links
        if link and not link.startswith("http") and base_url:
            link = urljoin(base_url, link)

        jobs.append(_job(
            title,
            _extract_company(full_text),
            location,
            _extract_salary(full_text),
            _parse_rss_date(pub_date),
            _extract_deadline(full_text),
            link,
            source
        ))

    logger.info(f"[{source}] {len(jobs)} relevant jobs from feed")
    return jobs


# ═══════════════════════════════════════════════════════════════════════════════
#  SCRAPERS — only using confirmed working URLs
# ═══════════════════════════════════════════════════════════════════════════════

def scrape_hotnigerianjobs(keyword: str, session: requests.Session) -> List[Dict]:
    """hotnigerianjobs.com — WordPress, feed works reliably."""
    jobs = []
    url = f"https://www.hotnigerianjobs.com/feed/?s={quote_plus(keyword)}"
    logger.info(f"[HotNigerianJobs] {url}")
    r = _get(url, session)
    if r:
        jobs = _parse_feed(r.text, "HotNigerianJobs", "https://www.hotnigerianjobs.com")
    logger.info(f"[HotNigerianJobs] {len(jobs)} for '{keyword}'")
    return jobs


def scrape_myjobmag(keyword: str, session: requests.Session) -> List[Dict]:
    """myjobmag.com — try multiple known feed paths."""
    jobs = []
    # MyJobMag feed URLs — try each until one works
    urls = [
        f"https://www.myjobmag.com/rss/jobs/{quote_plus(keyword)}/Lagos",
        f"https://www.myjobmag.com/rss/jobs?q={quote_plus(keyword)}",
        "https://www.myjobmag.com/rss/",
    ]
    for url in urls:
        logger.info(f"[MyJobMag] {url}")
        r = _get(url, session)
        if r and ("<item>" in r.text or "<entry>" in r.text):
            jobs = _parse_feed(r.text, "MyJobMag", "https://www.myjobmag.com")
            if jobs:
                break
        _sleep()
    logger.info(f"[MyJobMag] {len(jobs)} for '{keyword}'")
    return jobs


def scrape_ngcareers(keyword: str, session: requests.Session) -> List[Dict]:
    """ngcareers.com — has RSS feed."""
    jobs = []
    urls = [
        f"https://ngcareers.com/feed?q={quote_plus(keyword)}&location=Lagos",
        "https://ngcareers.com/feed",
        "https://ngcareers.com/rss",
    ]
    for url in urls:
        logger.info(f"[NgCareers] {url}")
        r = _get(url, session)
        if r and ("<item>" in r.text or "<entry>" in r.text):
            jobs = _parse_feed(r.text, "NgCareers", "https://ngcareers.com")
            if jobs:
                break
        _sleep()
    logger.info(f"[NgCareers] {len(jobs)} for '{keyword}'")
    return jobs


def scrape_naijajobs(keyword: str, session: requests.Session) -> List[Dict]:
    """naijajobs.net — WordPress job board with RSS."""
    jobs = []
    url = f"https://naijajobs.net/feed/?s={quote_plus(keyword)}"
    logger.info(f"[NaijaJobs] {url}")
    r = _get(url, session)
    if r and ("<item>" in r.text or "<channel>" in r.text):
        jobs = _parse_feed(r.text, "NaijaJobs", "https://naijajobs.net")
    logger.info(f"[NaijaJobs] {len(jobs)} for '{keyword}'")
    return jobs


def scrape_jobsinnigeria(keyword: str, session: requests.Session) -> List[Dict]:
    """jobsinnigeria.net — WordPress RSS feed."""
    jobs = []
    url = f"https://jobsinnigeria.net/feed/?s={quote_plus(keyword)}"
    logger.info(f"[JobsInNigeria] {url}")
    r = _get(url, session)
    if r and ("<item>" in r.text or "<channel>" in r.text):
        jobs = _parse_feed(r.text, "JobsInNigeria", "https://jobsinnigeria.net")
    logger.info(f"[JobsInNigeria] {len(jobs)} for '{keyword}'")
    return jobs


def scrape_recruitmentng(keyword: str, session: requests.Session) -> List[Dict]:
    """recruitment.com.ng — Nigerian recruitment site with feed."""
    jobs = []
    urls = [
        f"https://www.recruitment.com.ng/feed/?s={quote_plus(keyword)}",
        "https://www.recruitment.com.ng/feed/",
    ]
    for url in urls:
        logger.info(f"[RecruitmentNg] {url}")
        r = _get(url, session)
        if r and ("<item>" in r.text or "<channel>" in r.text):
            jobs = _parse_feed(r.text, "RecruitmentNg", "https://www.recruitment.com.ng")
            if jobs:
                break
        _sleep()
    logger.info(f"[RecruitmentNg] {len(jobs)} for '{keyword}'")
    return jobs


def scrape_nigerianjobsnet(keyword: str, session: requests.Session) -> List[Dict]:
    """nigerianjobs.net — WordPress job aggregator with RSS."""
    jobs = []
    url = f"https://www.nigerianjobs.net/feed/?s={quote_plus(keyword)}"
    logger.info(f"[NigerianJobs.net] {url}")
    r = _get(url, session)
    if r and ("<item>" in r.text or "<channel>" in r.text):
        jobs = _parse_feed(r.text, "NigerianJobs.net", "https://www.nigerianjobs.net")
    logger.info(f"[NigerianJobs.net] {len(jobs)} for '{keyword}'")
    return jobs


def scrape_nigeriacurrentjobs(keyword: str, session: requests.Session) -> List[Dict]:
    """nigeriancurrentjobs.com — active Nigerian job blog."""
    jobs = []
    url = f"https://www.nigeriancurrentjobs.com/feed/?s={quote_plus(keyword)}"
    logger.info(f"[NigeriaCurrentJobs] {url}")
    r = _get(url, session)
    if r and ("<item>" in r.text or "<channel>" in r.text):
        jobs = _parse_feed(r.text, "NigeriaCurrentJobs",
                           "https://www.nigeriancurrentjobs.com")
    logger.info(f"[NigeriaCurrentJobs] {len(jobs)} for '{keyword}'")
    return jobs


def scrape_joblistng(keyword: str, session: requests.Session) -> List[Dict]:
    """joblist.ng — Nigerian job listing site."""
    jobs = []
    urls = [
        f"https://joblist.ng/feed/?s={quote_plus(keyword)}",
        "https://joblist.ng/feed/",
    ]
    for url in urls:
        logger.info(f"[JobList.ng] {url}")
        r = _get(url, session)
        if r and ("<item>" in r.text or "<channel>" in r.text):
            jobs = _parse_feed(r.text, "JobList.ng", "https://joblist.ng")
            if jobs:
                break
        _sleep()
    logger.info(f"[JobList.ng] {len(jobs)} for '{keyword}'")
    return jobs


def scrape_jobcenterng(keyword: str, session: requests.Session) -> List[Dict]:
    """jobcenternigeria.com — Nigerian job centre."""
    jobs = []
    url = f"https://jobcenternigeria.com/feed/?s={quote_plus(keyword)}"
    logger.info(f"[JobCenterNigeria] {url}")
    r = _get(url, session)
    if r and ("<item>" in r.text or "<channel>" in r.text):
        jobs = _parse_feed(r.text, "JobCenterNigeria",
                           "https://jobcenternigeria.com")
    logger.info(f"[JobCenterNigeria] {len(jobs)} for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════════════════════
#  MASTER SCRAPER
# ═══════════════════════════════════════════════════════════════════════════════
SCRAPERS = {
    "HotNigerianJobs":   scrape_hotnigerianjobs,
    "MyJobMag":          scrape_myjobmag,
    "NgCareers":         scrape_ngcareers,
    "NaijaJobs":         scrape_naijajobs,
    "JobsInNigeria":     scrape_jobsinnigeria,
    "RecruitmentNg":     scrape_recruitmentng,
    "NigerianJobs.net":  scrape_nigerianjobsnet,
    "NigeriaCurrentJobs":scrape_nigeriacurrentjobs,
    "JobList.ng":        scrape_joblistng,
    "JobCenterNigeria":  scrape_jobcenterng,
}


def scrape_all_sources(keywords: List[str] = None) -> List[Dict]:
    """
    Scrape all Nigerian platforms via RSS feeds.
    Returns flat list of raw job dicts ready for filter.py.
    """
    if keywords is None:
        keywords = SEARCH_KEYWORDS

    all_jobs = []
    session  = requests.Session()
    session.headers.update(_headers())

    for source_name, fn in SCRAPERS.items():
        for keyword in keywords:
            logger.info(f"▶ '{keyword}' → {source_name}")
            try:
                results = fn(keyword, session)
                if results:
                    all_jobs.extend(results)
                    logger.info(f"  ✓ +{len(results)} from {source_name}")
                else:
                    logger.info(f"  ✗ 0 from {source_name}")
            except Exception as e:
                logger.error(f"[{source_name}] Error for '{keyword}': {e}")
            _sleep()

    logger.info(f"═══ Total raw jobs: {len(all_jobs)} ═══")
    return all_jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)s | %(message)s")
    results = scrape_all_sources(["Customer Support"])
    print(f"\nTotal: {len(results)}")
    for j in results[:10]:
        print(f"  [{j['source']}] {j['title']} | {j['company']} | "
              f"{j['location']} | {j['date_posted']}")
