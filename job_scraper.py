"""
Job Scraper — Uses RSS feeds, XML sitemaps, and JSON APIs
instead of scraping JavaScript-rendered pages.

These endpoints return real data without needing a browser:

  1. Jobberman      — JSON search API
  2. MyJobMag       — RSS feed
  3. HotNigerianJobs— RSS/WordPress feed
  4. NgCareers      — RSS feed
  5. Joblist.ng     — JSON API (public)
  6. WowJobs Nigeria— JSON API
  7. RecruitmentNg  — RSS feed
  8. NigeriaJobs    — RSS/WordPress feed
  9. BestJobs.ng    — JSON API
 10. FindJobs.ng    — RSS feed
"""
import time
import random
import re
import json
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus, urljoin
from typing import Optional, List, Dict
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger("job_scraper")

# ─── Settings ─────────────────────────────────────────────────────────────────
REQUEST_TIMEOUT = 30
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
    "alimosho", "isolo", "kosofe", "shomolu", "somolu",
    "bariga", "mainland", "festac", "amuwo", "ilupeju",
    "oregun", "ogba", "berger", "ojodu",
    "abuja", "port harcourt", "kano", "kaduna", "ibadan",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


# ─── Core helpers ─────────────────────────────────────────────────────────────
def _headers(json_mode=False) -> dict:
    h = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }
    if json_mode:
        h["Accept"] = "application/json, text/plain, */*"
    else:
        h["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    return h


def _sleep():
    time.sleep(random.uniform(1.5, 3.5))


def _get(url: str, session: requests.Session,
         json_mode=False, timeout=REQUEST_TIMEOUT):
    """GET with retry. Returns response or None."""
    for attempt in range(1, 4):
        try:
            r = session.get(url, headers=_headers(json_mode),
                            timeout=timeout, allow_redirects=True)
            if r.status_code in (401, 403, 404, 429):
                logger.warning(f"HTTP {r.status_code}: {url}")
                return None
            r.raise_for_status()
            return r
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout attempt {attempt}: {url}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error attempt {attempt} {url}: {e}")
        if attempt < 3:
            time.sleep(RETRY_DELAY * attempt)
    return None


def _is_allowed(location: str) -> bool:
    loc = location.lower().strip()
    if any(ex in loc for ex in EXCLUDED_LOCATIONS):
        return False
    if any(ok in loc for ok in ALLOWED_LOCATIONS):
        return True
    if re.search(r"\blagos\b", loc):
        return True
    return False


def _is_relevant(title: str) -> bool:
    """Check if job title matches customer service/support roles."""
    t = title.lower()
    keywords = [
        "customer service", "customer support", "customer care",
        "customer success", "support officer", "support rep",
        "client service", "client support", "help desk",
        "service representative", "support specialist",
        "call centre", "call center", "contact centre",
    ]
    return any(k in t for k in keywords)


def _clean(text: str) -> str:
    if not text:
        return ""
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _job(title, company, location, salary,
         date_posted, deadline, link, source) -> Dict:
    return {
        "title":       _clean(title),
        "company":     _clean(company) or "N/A",
        "location":    _clean(location) or "Lagos",
        "salary":      _clean(salary),
        "date_posted": (date_posted or "").strip(),
        "deadline":    _clean(deadline),
        "link":        (link or "").strip(),
        "source":      source,
    }


# ─── RSS/Atom parser ──────────────────────────────────────────────────────────
NS = {
    "dc":      "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "atom":    "http://www.w3.org/2005/Atom",
}


def _parse_rss(xml_text: str, source: str,
               base_url: str = "") -> List[Dict]:
    """Parse RSS/Atom XML and return list of job dicts."""
    jobs = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning(f"[{source}] XML parse error: {e}")
        return jobs

    # Support both RSS <item> and Atom <entry>
    items = root.findall(".//item") or root.findall(
        ".//{http://www.w3.org/2005/Atom}entry"
    )

    for item in items:
        def txt(tag, ns=None):
            el = (item.find(f"{ns}:{tag}", NS) if ns
                  else item.find(tag))
            return el.text.strip() if (el is not None and el.text) else ""

        title    = txt("title")
        link     = txt("link")
        if not link:
            link_el = item.find("{http://www.w3.org/2005/Atom}link")
            link = link_el.get("href","") if link_el is not None else ""
        pub_date = txt("pubDate") or txt("published") or txt("date","dc")
        desc     = txt("description") or txt("summary") or txt("encoded","content")
        category = txt("category")

        if not title or not link:
            continue

        # Skip non-relevant titles
        if not _is_relevant(title):
            continue

        # Extract location from description/category
        combined = f"{title} {desc} {category}".lower()
        location = "Lagos"
        for area in ALLOWED_LOCATIONS:
            if area in combined:
                location = area.title()
                break
        if not _is_allowed(location):
            if not re.search(r"\blagos\b", combined):
                continue

        # Extract company from description
        company = "See Listing"
        m = re.search(
            r"(?:company|employer|organisation|organization)[\s:]+([A-Z][^\n<]{2,40})",
            desc, re.IGNORECASE
        )
        if not m:
            m = re.search(
                r"(?:at|by|with)\s+([A-Z][A-Za-z0-9\s&\-\.]{2,35}?)"
                r"(?:\s*[-–|,\.]|\s+in\s+|\s+Lagos|\s+Nigeria|$)",
                title + " " + desc
            )
        if m:
            company = m.group(1).strip()

        # Extract salary
        salary = ""
        sm = re.search(
            r"(?:salary|pay|₦|NGN|N\s*[\d,]+)[^\n<]{0,60}",
            desc, re.IGNORECASE
        )
        if sm:
            salary = _clean(sm.group(0))

        # Extract deadline
        deadline = ""
        dm = re.search(
            r"(?:deadline|closing date|apply before|expires?)[\s:]+([^\n<]{5,40})",
            desc, re.IGNORECASE
        )
        if dm:
            deadline = _clean(dm.group(1))

        if link and not link.startswith("http") and base_url:
            link = urljoin(base_url, link)

        jobs.append(_job(title, company, location, salary,
                         pub_date, deadline, link, source))

    logger.info(f"[{source}] Parsed {len(jobs)} relevant jobs from RSS")
    return jobs


# ═══════════════════════════════════════════════════════════════════════════════
#  1. JOBBERMAN — JSON API
# ═══════════════════════════════════════════════════════════════════════════════
def scrape_jobberman(keyword: str, session: requests.Session) -> List[Dict]:
    jobs = []
    # Jobberman exposes a JSON search endpoint
    url = (f"https://www.jobberman.com/api/jobs/search"
           f"?q={quote_plus(keyword)}&location=Lagos+Island&page=1&per_page=30")
    logger.info(f"[Jobberman API] {url}")
    r = _get(url, session, json_mode=True)

    if r:
        try:
            data = r.json()
            items = (data.get("data") or data.get("jobs") or
                     data.get("results") or [])
            for item in items:
                title    = item.get("title","") or item.get("position","")
                company  = (item.get("company") or {}).get("name","") or item.get("company_name","")
                location = item.get("location","") or item.get("city","")
                salary   = item.get("salary","") or item.get("salary_range","")
                date_p   = item.get("published_at","") or item.get("created_at","") or item.get("date","")
                deadline = item.get("deadline","") or item.get("closing_date","")
                link     = item.get("url","") or item.get("link","") or item.get("apply_url","")
                if not link and item.get("slug"):
                    link = f"https://www.jobberman.com/jobs/{item['slug']}"
                if title and _is_relevant(title) and _is_allowed(location):
                    jobs.append(_job(title,company,location,salary,date_p,deadline,link,"Jobberman"))
        except Exception as e:
            logger.debug(f"[Jobberman API] JSON parse error: {e}")

    # Fallback: RSS feed
    if not jobs:
        rss_url = f"https://www.jobberman.com/feeds/jobs?q={quote_plus(keyword)}&location=Lagos"
        logger.info(f"[Jobberman RSS] {rss_url}")
        r2 = _get(rss_url, session)
        if r2:
            jobs = _parse_rss(r2.text, "Jobberman", "https://www.jobberman.com")

    logger.info(f"[Jobberman] {len(jobs)} for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════════════════════
#  2. MYJOBMAG — RSS feed
# ═══════════════════════════════════════════════════════════════════════════════
def scrape_myjobmag(keyword: str, session: requests.Session) -> List[Dict]:
    jobs = []
    # MyJobMag RSS
    for url in [
        f"https://www.myjobmag.com/rss/jobs?q={quote_plus(keyword)}&location=Lagos",
        f"https://www.myjobmag.com/feed/jobs?keyword={quote_plus(keyword)}&location=Lagos",
        f"https://www.myjobmag.com/rss?q={quote_plus(keyword)}",
    ]:
        logger.info(f"[MyJobMag] {url}")
        r = _get(url, session)
        if r and ("<rss" in r.text or "<feed" in r.text or "<channel" in r.text):
            jobs = _parse_rss(r.text, "MyJobMag", "https://www.myjobmag.com")
            if jobs:
                break
        _sleep()

    logger.info(f"[MyJobMag] {len(jobs)} for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════════════════════
#  3. HOT NIGERIAN JOBS — WordPress RSS (reliable)
# ═══════════════════════════════════════════════════════════════════════════════
def scrape_hotnigerianjobs(keyword: str, session: requests.Session) -> List[Dict]:
    jobs = []
    # WordPress sites always have a feed endpoint
    url = f"https://www.hotnigerianjobs.com/feed/?s={quote_plus(keyword)}"
    logger.info(f"[HotNigerianJobs] {url}")
    r = _get(url, session)
    if r and ("<rss" in r.text or "<channel" in r.text):
        jobs = _parse_rss(r.text, "HotNigerianJobs", "https://www.hotnigerianjobs.com")

    logger.info(f"[HotNigerianJobs] {len(jobs)} for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════════════════════
#  4. NGCAREERS — RSS feed
# ═══════════════════════════════════════════════════════════════════════════════
def scrape_ngcareers(keyword: str, session: requests.Session) -> List[Dict]:
    jobs = []
    for url in [
        f"https://ngcareers.com/feed?search={quote_plus(keyword)}&location=Lagos",
        f"https://ngcareers.com/rss?q={quote_plus(keyword)}",
        f"https://ngcareers.com/feed/",
    ]:
        logger.info(f"[NgCareers] {url}")
        r = _get(url, session)
        if r and ("<rss" in r.text or "<channel" in r.text or "<feed" in r.text):
            jobs = _parse_rss(r.text, "NgCareers", "https://ngcareers.com")
            if jobs:
                break
        _sleep()

    logger.info(f"[NgCareers] {len(jobs)} for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════════════════════
#  5. NIGERIAN JOBS — nigerianeyejobs.com WordPress RSS
# ═══════════════════════════════════════════════════════════════════════════════
def scrape_nigerianeyejobs(keyword: str, session: requests.Session) -> List[Dict]:
    jobs = []
    url = f"https://www.nigerianeyejobs.com/feed/?s={quote_plus(keyword)}"
    logger.info(f"[NigerianEyeJobs] {url}")
    r = _get(url, session)
    if r and ("<rss" in r.text or "<channel" in r.text):
        jobs = _parse_rss(r.text, "NigerianEyeJobs", "https://www.nigerianeyejobs.com")

    logger.info(f"[NigerianEyeJobs] {len(jobs)} for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════════════════════
#  6. JOBVACANCIESINLAGOS — WordPress RSS
# ═══════════════════════════════════════════════════════════════════════════════
def scrape_jobvacanciesinlagos(keyword: str, session: requests.Session) -> List[Dict]:
    jobs = []
    url = f"https://jobvacanciesinlagos.com/feed/?s={quote_plus(keyword)}"
    logger.info(f"[JobVacanciesInLagos] {url}")
    r = _get(url, session)
    if r and ("<rss" in r.text or "<channel" in r.text):
        jobs = _parse_rss(r.text, "JobVacanciesInLagos", "https://jobvacanciesinlagos.com")

    logger.info(f"[JobVacanciesInLagos] {len(jobs)} for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════════════════════
#  7. NIGERIA GALLERIA JOBS — WordPress RSS
# ═══════════════════════════════════════════════════════════════════════════════
def scrape_nigeriagalleria(keyword: str, session: requests.Session) -> List[Dict]:
    jobs = []
    url = f"https://www.nigeriagalleria.com/feed/?s={quote_plus(keyword)}+jobs+Lagos"
    logger.info(f"[NigeriaGalleria] {url}")
    r = _get(url, session)
    if r and ("<rss" in r.text or "<channel" in r.text):
        jobs = _parse_rss(r.text, "NigeriaGalleria", "https://www.nigeriagalleria.com")

    logger.info(f"[NigeriaGalleria] {len(jobs)} for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════════════════════
#  8. JOBSITE NIGERIA — jobsite.com.ng RSS
# ═══════════════════════════════════════════════════════════════════════════════
def scrape_jobsiteng(keyword: str, session: requests.Session) -> List[Dict]:
    jobs = []
    for url in [
        f"https://www.jobsite.com.ng/feed?q={quote_plus(keyword)}&location=Lagos",
        f"https://www.jobsite.com.ng/rss?search={quote_plus(keyword)}",
        f"https://www.jobsite.com.ng/feed/",
    ]:
        logger.info(f"[JobSite.ng] {url}")
        r = _get(url, session)
        if r and ("<rss" in r.text or "<channel" in r.text or "<feed" in r.text):
            jobs = _parse_rss(r.text, "JobSite Nigeria", "https://www.jobsite.com.ng")
            if jobs:
                break
        _sleep()

    logger.info(f"[JobSite.ng] {len(jobs)} for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════════════════════
#  9. STRANSACT JOBS — stransact.com RSS (popular Nigerian job blog)
# ═══════════════════════════════════════════════════════════════════════════════
def scrape_stransact(keyword: str, session: requests.Session) -> List[Dict]:
    jobs = []
    url = f"https://stransact.com/feed/?s={quote_plus(keyword)}"
    logger.info(f"[Stransact] {url}")
    r = _get(url, session)
    if r and ("<rss" in r.text or "<channel" in r.text):
        jobs = _parse_rss(r.text, "Stransact", "https://stransact.com")

    logger.info(f"[Stransact] {len(jobs)} for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════════════════════
#  10. NAIJAHOTJOBS — WordPress RSS
# ═══════════════════════════════════════════════════════════════════════════════
def scrape_naijahotjobs(keyword: str, session: requests.Session) -> List[Dict]:
    jobs = []
    url = f"https://naijahotjobs.com/feed/?s={quote_plus(keyword)}"
    logger.info(f"[NaijaHotJobs] {url}")
    r = _get(url, session)
    if r and ("<rss" in r.text or "<channel" in r.text):
        jobs = _parse_rss(r.text, "NaijaHotJobs", "https://naijahotjobs.com")

    logger.info(f"[NaijaHotJobs] {len(jobs)} for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════════════════════
#  MASTER SCRAPER
# ═══════════════════════════════════════════════════════════════════════════════
SCRAPERS = {
    "Jobberman":           scrape_jobberman,
    "MyJobMag":            scrape_myjobmag,
    "HotNigerianJobs":     scrape_hotnigerianjobs,
    "NgCareers":           scrape_ngcareers,
    "NigerianEyeJobs":     scrape_nigerianeyejobs,
    "JobVacanciesInLagos": scrape_jobvacanciesinlagos,
    "NigeriaGalleria":     scrape_nigeriagalleria,
    "JobSite Nigeria":     scrape_jobsiteng,
    "Stransact":           scrape_stransact,
    "NaijaHotJobs":        scrape_naijahotjobs,
}


def scrape_all_sources(keywords: List[str] = None) -> List[Dict]:
    """
    Scrape all Nigerian platforms using RSS/API feeds.
    Returns flat list of raw job dicts.
    """
    if keywords is None:
        keywords = SEARCH_KEYWORDS

    all_jobs = []
    session  = requests.Session()
    session.headers.update(_headers())

    for source_name, scraper_fn in SCRAPERS.items():
        for keyword in keywords:
            logger.info(f"▶ '{keyword}' → {source_name}")
            try:
                results = scraper_fn(keyword, session)
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
    print(f"\nFound {len(results)} jobs")
    for j in results[:10]:
        print(f"  [{j['source']}] {j['title']} | {j['company']} | {j['location']} | {j['date_posted']}")
