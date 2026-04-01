"""
Job Scraper — fetches raw job listings from multiple Nigerian platforms.
Each scraper returns a list of raw dicts; filtering happens in filter.py.
"""
import time
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote_plus
from typing import Optional

import config
from utils import logger, get_random_headers, with_retry


# ─── Base HTTP Helper ─────────────────────────────────────────────────────────
def fetch_page(url: str, session: Optional[requests.Session] = None) -> Optional[BeautifulSoup]:
    """Fetch a URL and return a BeautifulSoup object."""
    requester = session or requests
    headers = get_random_headers()
    try:
        resp = requester.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout fetching: {url}")
    except requests.exceptions.HTTPError as e:
        logger.warning(f"HTTP {e.response.status_code} for: {url}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Request error for {url}: {e}")
    return None


def polite_sleep():
    time.sleep(random.uniform(1.5, 3.5))


# ─── Jobberman Scraper ────────────────────────────────────────────────────────
def scrape_jobberman(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = f"https://www.jobberman.com/jobs?q={quote_plus(keyword)}&l=Lagos+Island"
    logger.info(f"[Jobberman] Scraping: {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    # Jobberman job cards (selector as of 2024–2025)
    cards = soup.select("div.mx-auto article, div[class*='job-card'], li.job-card")
    if not cards:
        cards = soup.select("article")

    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            title_el = card.select_one("h2 a, h3 a, a[class*='title'], .job-title a")
            company_el = card.select_one("[class*='company'], [class*='employer']")
            location_el = card.select_one("[class*='location'], [class*='city']")
            salary_el = card.select_one("[class*='salary'], [class*='pay']")
            date_el = card.select_one("time, [class*='date'], [class*='posted']")

            if not title_el:
                continue

            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin("https://www.jobberman.com", link)

            jobs.append({
                "title": title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "N/A",
                "location": location_el.get_text(strip=True) if location_el else "Lagos",
                "salary": salary_el.get_text(strip=True) if salary_el else "",
                "date_posted": date_el.get("datetime") or (date_el.get_text(strip=True) if date_el else ""),
                "deadline": "",
                "link": link,
                "source": "Jobberman",
            })
        except Exception as e:
            logger.debug(f"[Jobberman] Card parse error: {e}")

    logger.info(f"[Jobberman] Found {len(jobs)} raw listings for '{keyword}'")
    return jobs


# ─── MyJobMag Scraper ─────────────────────────────────────────────────────────
def scrape_myjobmag(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = f"https://www.myjobmag.com/jobs/search?query={quote_plus(keyword)}&location=Lagos+Island"
    logger.info(f"[MyJobMag] Scraping: {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    cards = soup.select("div.job-list-item, article.job-card, li[class*='job']")
    if not cards:
        cards = soup.select("article")

    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            title_el = card.select_one("h2 a, h3 a, a.job-title, [class*='title'] a")
            company_el = card.select_one("[class*='company'], [class*='employer'], h4")
            location_el = card.select_one("[class*='location'], [class*='city']")
            salary_el = card.select_one("[class*='salary']")
            date_el = card.select_one("time, [class*='date'], [class*='ago']")
            deadline_el = card.select_one("[class*='deadline'], [class*='expires']")

            if not title_el:
                continue

            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin("https://www.myjobmag.com", link)

            jobs.append({
                "title": title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "N/A",
                "location": location_el.get_text(strip=True) if location_el else "Lagos",
                "salary": salary_el.get_text(strip=True) if salary_el else "",
                "date_posted": date_el.get("datetime") or (date_el.get_text(strip=True) if date_el else ""),
                "deadline": deadline_el.get_text(strip=True) if deadline_el else "",
                "link": link,
                "source": "MyJobMag",
            })
        except Exception as e:
            logger.debug(f"[MyJobMag] Card parse error: {e}")

    logger.info(f"[MyJobMag] Found {len(jobs)} raw listings for '{keyword}'")
    return jobs


# ─── Hot Nigerian Jobs Scraper ────────────────────────────────────────────────
def scrape_hotnigerianjobs(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = f"https://www.hotnigerianjobs.com/?s={quote_plus(keyword)}"
    logger.info(f"[HotNigerianJobs] Scraping: {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    cards = soup.select("article.post, div.job-listing, div[class*='entry']")

    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            title_el = card.select_one("h2 a, h3 a, .entry-title a")
            date_el = card.select_one("time, .entry-date, [class*='date']")
            excerpt_el = card.select_one("p, .entry-summary, .excerpt")

            if not title_el:
                continue

            link = title_el.get("href", "")
            excerpt_text = excerpt_el.get_text(strip=True) if excerpt_el else ""

            # Extract location from excerpt/title heuristically
            location = "Lagos"
            for area in config.ALLOWED_LOCATIONS + config.EXCLUDED_LOCATIONS:
                if area.lower() in (excerpt_text + title_el.get_text()).lower():
                    location = area.title()
                    break

            jobs.append({
                "title": title_el.get_text(strip=True),
                "company": "See Listing",
                "location": location,
                "salary": "",
                "date_posted": date_el.get("datetime") or (date_el.get_text(strip=True) if date_el else ""),
                "deadline": "",
                "link": link,
                "source": "HotNigerianJobs",
            })
        except Exception as e:
            logger.debug(f"[HotNigerianJobs] Card parse error: {e}")

    logger.info(f"[HotNigerianJobs] Found {len(jobs)} raw listings for '{keyword}'")
    return jobs


# ─── Indeed Nigeria Scraper ───────────────────────────────────────────────────
def scrape_indeed(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = f"https://ng.indeed.com/jobs?q={quote_plus(keyword)}&l=Lagos+Island%2C+Lagos"
    logger.info(f"[Indeed] Scraping: {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    # Indeed job cards
    cards = soup.select("div.job_seen_beacon, div[class*='jobCard'], li[class*='css']")

    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            title_el = card.select_one("h2 a span, a[data-jk] span, .jobTitle a span")
            company_el = card.select_one("[data-testid='company-name'], .companyName")
            location_el = card.select_one("[data-testid='text-location'], .companyLocation")
            salary_el = card.select_one("[data-testid='attribute_snippet_testid'], .salary-snippet")
            date_el = card.select_one("span[class*='date'], [data-testid='myJobsStateDate']")
            link_el = card.select_one("h2 a, a[data-jk]")

            if not title_el:
                continue

            link = ""
            if link_el:
                href = link_el.get("href", "")
                link = urljoin("https://ng.indeed.com", href)

            jobs.append({
                "title": title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "N/A",
                "location": location_el.get_text(strip=True) if location_el else "Lagos",
                "salary": salary_el.get_text(strip=True) if salary_el else "",
                "date_posted": date_el.get_text(strip=True) if date_el else "",
                "deadline": "",
                "link": link,
                "source": "Indeed Nigeria",
            })
        except Exception as e:
            logger.debug(f"[Indeed] Card parse error: {e}")

    logger.info(f"[Indeed] Found {len(jobs)} raw listings for '{keyword}'")
    return jobs


# ─── LinkedIn Scraper (Public API) ────────────────────────────────────────────
def scrape_linkedin(keyword: str, session: requests.Session) -> list:
    jobs = []
    # LinkedIn public jobs page (no auth needed for listing)
    url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={quote_plus(keyword)}"
        f"&location=Lagos%20Island%2C%20Lagos%2C%20Nigeria"
        f"&f_TP=1%2C2"   # posted in past 24–48 hours
        f"&f_JT=F%2CP"   # full-time, part-time
    )
    logger.info(f"[LinkedIn] Scraping: {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    cards = soup.select("div.base-card, li.jobs-search__results-list > div, li.result-card")

    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            title_el = card.select_one("h3.base-search-card__title, span.screen-reader-text")
            company_el = card.select_one("h4.base-search-card__subtitle, a.hidden-nested-link")
            location_el = card.select_one("span.job-search-card__location")
            date_el = card.select_one("time")
            link_el = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")

            if not title_el:
                continue

            link = link_el.get("href", "") if link_el else ""

            jobs.append({
                "title": title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "N/A",
                "location": location_el.get_text(strip=True) if location_el else "Lagos",
                "salary": "",
                "date_posted": date_el.get("datetime") or (date_el.get_text(strip=True) if date_el else ""),
                "deadline": "",
                "link": link,
                "source": "LinkedIn",
            })
        except Exception as e:
            logger.debug(f"[LinkedIn] Card parse error: {e}")

    logger.info(f"[LinkedIn] Found {len(jobs)} raw listings for '{keyword}'")
    return jobs


# ─── Master Scraper ───────────────────────────────────────────────────────────
SCRAPERS = {
    "jobberman": scrape_jobberman,
    "myjobmag": scrape_myjobmag,
    "hotnigerianjobs": scrape_hotnigerianjobs,
    "indeed": scrape_indeed,
    "linkedin": scrape_linkedin,
}


def scrape_all_sources() -> list:
    """Run all scrapers for all keywords; return combined raw job list."""
    all_jobs = []
    session = requests.Session()
    session.headers.update(get_random_headers())

    for source_name, scraper_fn in SCRAPERS.items():
        if not config.JOB_SOURCES.get(source_name, {}).get("enabled", True):
            logger.info(f"[{source_name}] Disabled — skipping.")
            continue

        for keyword in config.SEARCH_KEYWORDS:
            logger.info(f"Scraping '{keyword}' from {source_name} ...")
            try:
                results = with_retry(scraper_fn, keyword, session)
                if results:
                    all_jobs.extend(results)
            except Exception as e:
                logger.error(f"[{source_name}] Unexpected error for '{keyword}': {e}")
            polite_sleep()

    logger.info(f"Total raw jobs collected: {len(all_jobs)}")
    return all_jobs
