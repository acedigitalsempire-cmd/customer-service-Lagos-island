"""
Job Scraper — Nigerian job platforms ONLY. LinkedIn removed entirely.

Platforms:
  1. Jobberman         (jobberman.com)
  2. MyJobMag          (myjobmag.com)
  3. HotNigerianJobs   (hotnigerianjobs.com)
  4. Indeed Nigeria    (ng.indeed.com)
  5. NgCareers         (ngcareers.com)
  6. Jobgurus Nigeria  (jobgurus.com.ng)
  7. PunchJobs         (jobs.punchng.com)
  8. Careers24 Nigeria (careers24.com)
  9. Graduatejobs.ng   (graduatejobs.ng)
 10. Recruitment.ng    (recruitment.com.ng / alternately search via Google)
"""
import time
import random
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus
from typing import Optional

import config
from utils import logger, get_random_headers, with_retry


# ─── HTTP Fetcher ─────────────────────────────────────────────────────────────
def fetch_page(url: str, session: Optional[requests.Session] = None,
               extra_headers: dict = None) -> Optional[BeautifulSoup]:
    requester = session or requests
    headers = get_random_headers()
    if extra_headers:
        headers.update(extra_headers)
    try:
        resp = requester.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT)
        if resp.status_code in (401, 403, 429):
            logger.warning(f"HTTP {resp.status_code} blocked: {url}")
            return None
        resp.raise_for_status()
        if len(resp.text) < 400:
            logger.warning(f"Too-short response ({len(resp.text)}): {url}")
            return None
        return BeautifulSoup(resp.text, "html.parser")
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout: {url}")
    except requests.exceptions.HTTPError as e:
        logger.warning(f"HTTP error {url}: {e}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Request error {url}: {e}")
    return None


def polite_sleep():
    time.sleep(random.uniform(2.5, 5.0))


# ─── Date extractor (works across all sites) ─────────────────────────────────
def _get_date(soup_el: BeautifulSoup) -> str:
    """Try every common date pattern in a card/article element."""
    # 1. Dedicated date attributes
    for sel in ["time", "[class*='date']", "[class*='posted']",
                "[class*='ago']", "[class*='time']", "[class*='publish']",
                "[class*='created']", "[data-date]", "[data-time]"]:
        el = soup_el.select_one(sel)
        if el:
            val = (el.get("datetime") or el.get("data-date") or
                   el.get("data-time") or el.get_text(strip=True))
            if val and len(val.strip()) > 2:
                return val.strip()
    # 2. Regex on full text
    text = soup_el.get_text(" ", strip=True)
    m = re.search(
        r"(\d+\s*(second|minute|hour|day|week)s?\s*ago"
        r"|just now|moments? ago|today|yesterday"
        r"|\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4}"
        r"|\d{4}-\d{2}-\d{2})",
        text, re.I
    )
    return m.group(0) if m else ""


def _get_meta_date(soup: BeautifulSoup) -> str:
    """Pull published_time from Open Graph / article meta tags."""
    for prop in ["article:published_time", "og:published_time",
                 "datePublished", "date"]:
        tag = soup.find("meta", {"property": prop}) or soup.find("meta", {"name": prop})
        if tag and tag.get("content"):
            return tag["content"]
    return ""


def _build_job(title, company, location, salary, date_posted,
               deadline, link, source) -> dict:
    return {
        "title":       title.strip(),
        "company":     (company or "N/A").strip(),
        "location":    (location or "Lagos").strip(),
        "salary":      (salary or "").strip(),
        "date_posted": (date_posted or "").strip(),
        "deadline":    (deadline or "").strip(),
        "link":        link.strip() if link else "",
        "source":      source,
    }


# ═══════════════════════════════════════════════════════════════
#  1. JOBBERMAN
# ═══════════════════════════════════════════════════════════════
def scrape_jobberman(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = f"https://www.jobberman.com/jobs?q={quote_plus(keyword)}&l=Lagos+Island"
    logger.info(f"[Jobberman] {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    cards = soup.select("article, div[class*='job-card'], li[class*='job-listing']")
    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            t = card.select_one("h2 a, h3 a, a[class*='title'], .job-title a, [class*='title'] a")
            c = card.select_one("[class*='company'], [class*='employer'], [class*='recruiter']")
            l = card.select_one("[class*='location'], [class*='city'], [class*='address']")
            s = card.select_one("[class*='salary'], [class*='pay'], [class*='remuneration']")
            if not t:
                continue
            link = t.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin("https://www.jobberman.com", link)
            jobs.append(_build_job(
                t.get_text(strip=True),
                c.get_text(strip=True) if c else "N/A",
                l.get_text(strip=True) if l else "Lagos Island",
                s.get_text(strip=True) if s else "",
                _get_date(card), "", link, "Jobberman"
            ))
        except Exception as e:
            logger.debug(f"[Jobberman] {e}")

    logger.info(f"[Jobberman] {len(jobs)} raw for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════
#  2. MYJOBMAG
# ═══════════════════════════════════════════════════════════════
def scrape_myjobmag(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = f"https://www.myjobmag.com/jobs/search?query={quote_plus(keyword)}&location=Lagos+Island"
    logger.info(f"[MyJobMag] {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    cards = soup.select("div.job-list-item, article, li[class*='job'], div[class*='job-item']")
    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            t  = card.select_one("h2 a, h3 a, a.job-title, [class*='title'] a")
            c  = card.select_one("[class*='company'], [class*='employer'], h4")
            l  = card.select_one("[class*='location'], [class*='city']")
            s  = card.select_one("[class*='salary']")
            dl = card.select_one("[class*='deadline'], [class*='expires'], [class*='closing']")
            if not t:
                continue
            link = t.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin("https://www.myjobmag.com", link)
            jobs.append(_build_job(
                t.get_text(strip=True),
                c.get_text(strip=True) if c else "N/A",
                l.get_text(strip=True) if l else "Lagos Island",
                s.get_text(strip=True) if s else "",
                _get_date(card),
                dl.get_text(strip=True) if dl else "",
                link, "MyJobMag"
            ))
        except Exception as e:
            logger.debug(f"[MyJobMag] {e}")

    logger.info(f"[MyJobMag] {len(jobs)} raw for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════
#  3. HOT NIGERIAN JOBS
# ═══════════════════════════════════════════════════════════════
def scrape_hotnigerianjobs(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = f"https://www.hotnigerianjobs.com/?s={quote_plus(keyword)}"
    logger.info(f"[HotNigerianJobs] {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    cards = soup.select("article.post, div.post, div[class*='entry']")
    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            t = card.select_one("h2 a, h3 a, .entry-title a")
            if not t:
                continue
            link      = t.get("href", "")
            date_text = _get_date(card)

            # Fetch the post page for the date if not on listing
            if not date_text and link:
                post = with_retry(fetch_page, link, session)
                if post:
                    date_text = _get_meta_date(post) or _get_date(post)
                polite_sleep()

            card_text = card.get_text(" ", strip=True)
            location  = "Lagos"
            for area in config.ALLOWED_LOCATIONS:
                if area.lower() in card_text.lower():
                    location = area.title()
                    break

            company = "See Listing"
            m = re.search(
                r"(?:at|by|with)\s+([A-Z][A-Za-z0-9\s&\-\.]{2,40}?)"
                r"(?:\s*[-–|,]|\s+in\s+|\s+Lagos|\s+Nigeria|$)",
                card_text
            )
            if m:
                company = m.group(1).strip()

            jobs.append(_build_job(
                t.get_text(strip=True), company, location,
                "", date_text, "", link, "HotNigerianJobs"
            ))
        except Exception as e:
            logger.debug(f"[HotNigerianJobs] {e}")

    logger.info(f"[HotNigerianJobs] {len(jobs)} raw for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════
#  4. INDEED NIGERIA
# ═══════════════════════════════════════════════════════════════
def scrape_indeed(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = (f"https://ng.indeed.com/jobs?q={quote_plus(keyword)}"
           f"&l=Lagos+Island%2C+Lagos&fromage=2")
    logger.info(f"[Indeed] {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        logger.warning("[Indeed] Blocked — skipping.")
        return jobs

    cards = soup.select("div.job_seen_beacon, div[class*='jobCard'], li[class*='css-']")
    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            t    = card.select_one("h2 a span[title], h2 span[title], .jobTitle span")
            c    = card.select_one("[data-testid='company-name'], .companyName")
            l    = card.select_one("[data-testid='text-location'], .companyLocation")
            s    = card.select_one("[data-testid='attribute_snippet_testid'], .salary-snippet")
            link_el = card.select_one("h2 a, a[data-jk]")
            if not t:
                continue
            link = urljoin("https://ng.indeed.com", link_el.get("href","")) if link_el else ""
            jobs.append(_build_job(
                t.get("title") or t.get_text(strip=True),
                c.get_text(strip=True) if c else "N/A",
                l.get_text(strip=True) if l else "Lagos",
                s.get_text(strip=True) if s else "",
                _get_date(card), "", link, "Indeed Nigeria"
            ))
        except Exception as e:
            logger.debug(f"[Indeed] {e}")

    logger.info(f"[Indeed] {len(jobs)} raw for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════
#  5. NGCAREERS
# ═══════════════════════════════════════════════════════════════
def scrape_ngcareers(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = f"https://ngcareers.com/jobs?search={quote_plus(keyword)}&location=Lagos"
    logger.info(f"[NgCareers] {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    cards = soup.select("div.job-listing, article, div[class*='job'], li[class*='job']")
    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            t = card.select_one("h2 a, h3 a, [class*='title'] a, a[class*='job']")
            c = card.select_one("[class*='company'], [class*='employer']")
            l = card.select_one("[class*='location'], [class*='city']")
            s = card.select_one("[class*='salary']")
            if not t:
                continue
            link = t.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin("https://ngcareers.com", link)
            jobs.append(_build_job(
                t.get_text(strip=True),
                c.get_text(strip=True) if c else "N/A",
                l.get_text(strip=True) if l else "Lagos",
                s.get_text(strip=True) if s else "",
                _get_date(card), "", link, "NgCareers"
            ))
        except Exception as e:
            logger.debug(f"[NgCareers] {e}")

    logger.info(f"[NgCareers] {len(jobs)} raw for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════
#  6. JOBGURUS NIGERIA
# ═══════════════════════════════════════════════════════════════
def scrape_jobgurus(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = f"https://www.jobgurus.com.ng/search-jobs/?q={quote_plus(keyword)}&location=Lagos"
    logger.info(f"[JobGurus] {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    cards = soup.select("div.job-item, article.job, div[class*='job-card'], li[class*='job']")
    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            t = card.select_one("h2 a, h3 a, a[class*='title'], [class*='job-title'] a")
            c = card.select_one("[class*='company'], [class*='employer']")
            l = card.select_one("[class*='location'], [class*='city']")
            s = card.select_one("[class*='salary']")
            dl = card.select_one("[class*='deadline'], [class*='expir']")
            if not t:
                continue
            link = t.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin("https://www.jobgurus.com.ng", link)
            jobs.append(_build_job(
                t.get_text(strip=True),
                c.get_text(strip=True) if c else "N/A",
                l.get_text(strip=True) if l else "Lagos",
                s.get_text(strip=True) if s else "",
                _get_date(card),
                dl.get_text(strip=True) if dl else "",
                link, "JobGurus Nigeria"
            ))
        except Exception as e:
            logger.debug(f"[JobGurus] {e}")

    logger.info(f"[JobGurus] {len(jobs)} raw for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════
#  7. PUNCH JOBS  (jobs.punchng.com)
# ═══════════════════════════════════════════════════════════════
def scrape_punchjobs(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = f"https://jobs.punchng.com/?s={quote_plus(keyword)}&post_type=job_listing"
    logger.info(f"[PunchJobs] {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    cards = soup.select("li.job_listing, article.job_listing, div[class*='job_listing'], ul.job-listings li")
    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            t  = card.select_one("h3 a, h2 a, a.job-title, [class*='job-title'] a")
            c  = card.select_one("[class*='company'], strong.company, .company")
            l  = card.select_one("[class*='location'], .location, [class*='city']")
            s  = card.select_one("[class*='salary']")
            dl = card.select_one("[class*='deadline'], [class*='date'] strong, .job-expiry")
            if not t:
                continue
            link = t.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin("https://jobs.punchng.com", link)
            jobs.append(_build_job(
                t.get_text(strip=True),
                c.get_text(strip=True) if c else "N/A",
                l.get_text(strip=True) if l else "Lagos",
                s.get_text(strip=True) if s else "",
                _get_date(card),
                dl.get_text(strip=True) if dl else "",
                link, "PunchJobs"
            ))
        except Exception as e:
            logger.debug(f"[PunchJobs] {e}")

    logger.info(f"[PunchJobs] {len(jobs)} raw for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════
#  8. CAREERS24 NIGERIA
# ═══════════════════════════════════════════════════════════════
def scrape_careers24(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = (f"https://www.careers24.com/jobs/in-lagos/?keyword={quote_plus(keyword)}"
           f"&location=Lagos&country=ng")
    logger.info(f"[Careers24] {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    cards = soup.select("div.job-card, article.listing, li[class*='job'], div[class*='listing']")
    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            t = card.select_one("h2 a, h3 a, a[class*='title'], [class*='title'] a")
            c = card.select_one("[class*='company'], [class*='employer']")
            l = card.select_one("[class*='location'], [class*='city']")
            s = card.select_one("[class*='salary']")
            if not t:
                continue
            link = t.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin("https://www.careers24.com", link)
            jobs.append(_build_job(
                t.get_text(strip=True),
                c.get_text(strip=True) if c else "N/A",
                l.get_text(strip=True) if l else "Lagos",
                s.get_text(strip=True) if s else "",
                _get_date(card), "", link, "Careers24 Nigeria"
            ))
        except Exception as e:
            logger.debug(f"[Careers24] {e}")

    logger.info(f"[Careers24] {len(jobs)} raw for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════
#  9. GRADUATE JOBS NIGERIA  (graduatejobs.ng)
# ═══════════════════════════════════════════════════════════════
def scrape_graduatejobs(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = f"https://graduatejobs.ng/?s={quote_plus(keyword)}"
    logger.info(f"[GraduateJobs.ng] {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    cards = soup.select("article.post, div.job-post, div[class*='entry'], li[class*='job']")
    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            t = card.select_one("h2 a, h3 a, .entry-title a, [class*='title'] a")
            if not t:
                continue
            link      = t.get("href", "")
            date_text = _get_date(card)

            if not date_text and link:
                post = with_retry(fetch_page, link, session)
                if post:
                    date_text = _get_meta_date(post) or _get_date(post)
                polite_sleep()

            card_text = card.get_text(" ", strip=True)
            location  = "Lagos"
            for area in config.ALLOWED_LOCATIONS:
                if area.lower() in card_text.lower():
                    location = area.title()
                    break

            c_match = re.search(
                r"(?:at|by)\s+([A-Z][A-Za-z0-9\s&\-]{2,35}?)"
                r"(?:\s*[-–|,]|\s+in\s+|\s+Lagos|$)", card_text
            )
            company = c_match.group(1).strip() if c_match else "See Listing"

            jobs.append(_build_job(
                t.get_text(strip=True), company, location,
                "", date_text, "", link, "GraduateJobs.ng"
            ))
        except Exception as e:
            logger.debug(f"[GraduateJobs] {e}")

    logger.info(f"[GraduateJobs.ng] {len(jobs)} raw for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════
#  10. WORK IN NIGERIA  (workingnigeria.com)
# ═══════════════════════════════════════════════════════════════
def scrape_workingnigeria(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = f"https://www.workingnigeria.com/search/?q={quote_plus(keyword)}&location=Lagos"
    logger.info(f"[WorkingNigeria] {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    cards = soup.select("div.job-item, article, li[class*='job'], div[class*='vacancy']")
    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            t = card.select_one("h2 a, h3 a, [class*='title'] a, a[class*='job']")
            c = card.select_one("[class*='company'], [class*='employer'], [class*='organization']")
            l = card.select_one("[class*='location'], [class*='city']")
            s = card.select_one("[class*='salary']")
            if not t:
                continue
            link = t.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin("https://www.workingnigeria.com", link)
            jobs.append(_build_job(
                t.get_text(strip=True),
                c.get_text(strip=True) if c else "N/A",
                l.get_text(strip=True) if l else "Lagos",
                s.get_text(strip=True) if s else "",
                _get_date(card), "", link, "WorkingNigeria"
            ))
        except Exception as e:
            logger.debug(f"[WorkingNigeria] {e}")

    logger.info(f"[WorkingNigeria] {len(jobs)} raw for '{keyword}'")
    return jobs


# ═══════════════════════════════════════════════════════════════
#  MASTER SCRAPER  — LinkedIn is NOT here
# ═══════════════════════════════════════════════════════════════
SCRAPERS = {
    "jobberman":       scrape_jobberman,
    "myjobmag":        scrape_myjobmag,
    "hotnigerianjobs": scrape_hotnigerianjobs,
    "indeed":          scrape_indeed,
    "ngcareers":       scrape_ngcareers,
    "jobgurus":        scrape_jobgurus,
    "punchjobs":       scrape_punchjobs,
    "careers24":       scrape_careers24,
    "graduatejobs":    scrape_graduatejobs,
    "workingnigeria":  scrape_workingnigeria,
}


def scrape_all_sources() -> list:
    all_jobs = []
    session  = requests.Session()
    session.headers.update(get_random_headers())

    for source_name, scraper_fn in SCRAPERS.items():
        # Honour per-source enable/disable flag in config
        if not config.JOB_SOURCES.get(source_name, {}).get("enabled", True):
            logger.info(f"[{source_name}] Disabled in config — skipping.")
            continue

        for keyword in config.SEARCH_KEYWORDS:
            logger.info(f"▶ '{keyword}' → {source_name}")
            try:
                results = with_retry(scraper_fn, keyword, session)
                if results:
                    all_jobs.extend(results)
                    logger.info(f"  +{len(results)} from {source_name}")
                else:
                    logger.info(f"  0 from {source_name}")
            except Exception as e:
                logger.error(f"[{source_name}] Error for '{keyword}': {e}")
            polite_sleep()

    logger.info(f"═══ Total raw jobs collected: {len(all_jobs)} ═══")
    return all_jobs
