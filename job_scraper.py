"""
Job Scraper — fetches raw job listings from multiple Nigerian platforms.
Improved: better date extraction, graceful 403 handling, LinkedIn fallback.
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


# ─── Base HTTP Helper ─────────────────────────────────────────────────────────
def fetch_page(url: str, session: Optional[requests.Session] = None) -> Optional[BeautifulSoup]:
    requester = session or requests
    headers = get_random_headers()
    try:
        resp = requester.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT)
        if resp.status_code in (401, 403, 429):
            logger.warning(f"HTTP {resp.status_code} (blocked) for: {url}")
            return None
        resp.raise_for_status()
        if len(resp.text) < 500:
            logger.warning(f"Suspiciously short response ({len(resp.text)} chars): {url}")
            return None
        return BeautifulSoup(resp.text, "html.parser")
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout: {url}")
    except requests.exceptions.HTTPError as e:
        logger.warning(f"HTTP error for {url}: {e}")
    except requests.exceptions.RequestException as e:
        logger.warning(f"Request error for {url}: {e}")
    return None


def polite_sleep():
    time.sleep(random.uniform(2.0, 4.5))


# ─── Generic date extractor ───────────────────────────────────────────────────
def _extract_date_text(card: BeautifulSoup) -> str:
    selectors = [
        "time", "[class*='date']", "[class*='posted']",
        "[class*='ago']", "[class*='time']", "[class*='when']", "[data-date]",
    ]
    for sel in selectors:
        el = card.select_one(sel)
        if el:
            val = el.get("datetime") or el.get("data-date") or el.get_text(strip=True)
            if val and len(val) > 2:
                return val
    # Scan full text for relative time patterns
    text = card.get_text(" ", strip=True)
    match = re.search(r"(\d+\s*(minute|hour|day|week)s?\s*ago|just now|today|yesterday)", text, re.I)
    return match.group(0) if match else ""


# ─── Jobberman ────────────────────────────────────────────────────────────────
def scrape_jobberman(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = f"https://www.jobberman.com/jobs?q={quote_plus(keyword)}&l=Lagos+Island"
    logger.info(f"[Jobberman] {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    cards = soup.select("article, div[class*='job-card'], li[class*='job']")
    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            title_el = card.select_one("h2 a, h3 a, a[class*='title'], .job-title a, [class*='title'] a")
            company_el = card.select_one("[class*='company'], [class*='employer'], [class*='recruiter']")
            location_el = card.select_one("[class*='location'], [class*='city'], [class*='address']")
            salary_el = card.select_one("[class*='salary'], [class*='pay'], [class*='remuneration']")
            if not title_el:
                continue
            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin("https://www.jobberman.com", link)
            jobs.append({
                "title": title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "N/A",
                "location": location_el.get_text(strip=True) if location_el else "Lagos Island",
                "salary": salary_el.get_text(strip=True) if salary_el else "",
                "date_posted": _extract_date_text(card),
                "deadline": "",
                "link": link,
                "source": "Jobberman",
            })
        except Exception as e:
            logger.debug(f"[Jobberman] parse error: {e}")
    logger.info(f"[Jobberman] {len(jobs)} raw for '{keyword}'")
    return jobs


# ─── MyJobMag ─────────────────────────────────────────────────────────────────
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
            title_el = card.select_one("h2 a, h3 a, a.job-title, [class*='title'] a")
            company_el = card.select_one("[class*='company'], [class*='employer'], h4")
            location_el = card.select_one("[class*='location'], [class*='city']")
            salary_el = card.select_one("[class*='salary']")
            deadline_el = card.select_one("[class*='deadline'], [class*='expires'], [class*='closing']")
            if not title_el:
                continue
            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin("https://www.myjobmag.com", link)
            jobs.append({
                "title": title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "N/A",
                "location": location_el.get_text(strip=True) if location_el else "Lagos Island",
                "salary": salary_el.get_text(strip=True) if salary_el else "",
                "date_posted": _extract_date_text(card),
                "deadline": deadline_el.get_text(strip=True) if deadline_el else "",
                "link": link,
                "source": "MyJobMag",
            })
        except Exception as e:
            logger.debug(f"[MyJobMag] parse error: {e}")
    logger.info(f"[MyJobMag] {len(jobs)} raw for '{keyword}'")
    return jobs


# ─── Hot Nigerian Jobs ────────────────────────────────────────────────────────
def scrape_hotnigerianjobs(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = f"https://www.hotnigerianjobs.com/?s={quote_plus(keyword)}"
    logger.info(f"[HotNigerianJobs] {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    cards = soup.select("article.post, div.post, div[class*='entry'], div[class*='listing']")
    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            title_el = card.select_one("h2 a, h3 a, .entry-title a, h1 a")
            if not title_el:
                continue
            link = title_el.get("href", "")
            date_text = _extract_date_text(card)

            # Scrape individual post page for date if not found on listing
            if not date_text and link:
                post_soup = with_retry(fetch_page, link, session)
                if post_soup:
                    date_text = _extract_date_text(post_soup)
                    meta = post_soup.find("meta", {"property": "article:published_time"})
                    if meta and not date_text:
                        date_text = meta.get("content", "")
                polite_sleep()

            card_text = card.get_text(" ", strip=True)
            location = "Lagos Island"
            for area in config.ALLOWED_LOCATIONS + config.EXCLUDED_LOCATIONS:
                if area.lower() in card_text.lower():
                    location = area.title()
                    break

            company = "See Listing"
            m = re.search(r"at\s+([A-Z][A-Za-z\s&]+?)(?:\s*[-–|]|\s+in\s+|\s+Lagos)", card_text)
            if m:
                company = m.group(1).strip()

            jobs.append({
                "title": title_el.get_text(strip=True),
                "company": company,
                "location": location,
                "salary": "",
                "date_posted": date_text,
                "deadline": "",
                "link": link,
                "source": "HotNigerianJobs",
            })
        except Exception as e:
            logger.debug(f"[HotNigerianJobs] parse error: {e}")
    logger.info(f"[HotNigerianJobs] {len(jobs)} raw for '{keyword}'")
    return jobs


# ─── Indeed Nigeria ───────────────────────────────────────────────────────────
def scrape_indeed(keyword: str, session: requests.Session) -> list:
    jobs = []
    # fromage=2 = last 2 days
    url = f"https://ng.indeed.com/jobs?q={quote_plus(keyword)}&l=Lagos+Island%2C+Lagos&fromage=2"
    logger.info(f"[Indeed] {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        logger.warning("[Indeed] Blocked — skipping.")
        return jobs

    cards = soup.select("div.job_seen_beacon, div[class*='jobCard'], li[class*='css-']")
    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            title_el = card.select_one("h2 a span[title], h2 span[title], .jobTitle span")
            company_el = card.select_one("[data-testid='company-name'], .companyName, [class*='company']")
            location_el = card.select_one("[data-testid='text-location'], .companyLocation, [class*='location']")
            salary_el = card.select_one("[data-testid='attribute_snippet_testid'], .salary-snippet, [class*='salary']")
            link_el = card.select_one("h2 a, a[data-jk], a[id*='job_']")
            if not title_el:
                continue
            link = urljoin("https://ng.indeed.com", link_el.get("href", "")) if link_el else ""
            jobs.append({
                "title": title_el.get("title") or title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "N/A",
                "location": location_el.get_text(strip=True) if location_el else "Lagos",
                "salary": salary_el.get_text(strip=True) if salary_el else "",
                "date_posted": _extract_date_text(card),
                "deadline": "",
                "link": link,
                "source": "Indeed Nigeria",
            })
        except Exception as e:
            logger.debug(f"[Indeed] parse error: {e}")
    logger.info(f"[Indeed] {len(jobs)} raw for '{keyword}'")
    return jobs


# ─── LinkedIn (graceful — heavily JS-rendered) ────────────────────────────────
def scrape_linkedin(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={quote_plus(keyword)}"
        f"&location=Lagos%20Island%2C%20Lagos%2C%20Nigeria"
        f"&f_TPR=r86400&count=25"
    )
    logger.info(f"[LinkedIn] {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        logger.warning("[LinkedIn] Blocked or JS-only — skipping.")
        return jobs

    cards = soup.select(
        "div.base-card, li.result-card, div[class*='job-search-card'], div[data-entity-urn]"
    )
    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            title_el = card.select_one("h3.base-search-card__title, h3[class*='title'], span.screen-reader-text")
            company_el = card.select_one("h4.base-search-card__subtitle, a[class*='company'], h4")
            location_el = card.select_one("span.job-search-card__location, [class*='location']")
            date_el = card.select_one("time, [class*='listdate'], [class*='date']")
            link_el = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")
            if not title_el:
                continue
            link = link_el.get("href", "").split("?")[0] if link_el else ""
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
            logger.debug(f"[LinkedIn] parse error: {e}")
    logger.info(f"[LinkedIn] {len(jobs)} raw for '{keyword}'")
    return jobs


# ─── NgCareers (bonus — less blocking) ───────────────────────────────────────
def scrape_ngcareers(keyword: str, session: requests.Session) -> list:
    jobs = []
    url = f"https://ngcareers.com/jobs?search={quote_plus(keyword)}&location=Lagos+Island"
    logger.info(f"[NgCareers] {url}")
    soup = with_retry(fetch_page, url, session)
    if not soup:
        return jobs

    cards = soup.select("div.job-listing, article, div[class*='job']")
    for card in cards[:config.MAX_JOBS_PER_SOURCE]:
        try:
            title_el = card.select_one("h2 a, h3 a, [class*='title'] a")
            company_el = card.select_one("[class*='company'], [class*='employer']")
            location_el = card.select_one("[class*='location'], [class*='city']")
            salary_el = card.select_one("[class*='salary']")
            if not title_el:
                continue
            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin("https://ngcareers.com", link)
            jobs.append({
                "title": title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "N/A",
                "location": location_el.get_text(strip=True) if location_el else "Lagos Island",
                "salary": salary_el.get_text(strip=True) if salary_el else "",
                "date_posted": _extract_date_text(card),
                "deadline": "",
                "link": link,
                "source": "NgCareers",
            })
        except Exception as e:
            logger.debug(f"[NgCareers] parse error: {e}")
    logger.info(f"[NgCareers] {len(jobs)} raw for '{keyword}'")
    return jobs


# ─── Master Scraper ───────────────────────────────────────────────────────────
SCRAPERS = {
    "jobberman": scrape_jobberman,
    "myjobmag": scrape_myjobmag,
    "hotnigerianjobs": scrape_hotnigerianjobs,
    "indeed": scrape_indeed,
    "linkedin": scrape_linkedin,
    "ngcareers": scrape_ngcareers,
}


def scrape_all_sources() -> list:
    all_jobs = []
    session = requests.Session()
    session.headers.update(get_random_headers())

    for source_name, scraper_fn in SCRAPERS.items():
        if not config.JOB_SOURCES.get(source_name, {}).get("enabled", True):
            logger.info(f"[{source_name}] Disabled — skipping.")
            continue
        for keyword in config.SEARCH_KEYWORDS:
            logger.info(f"▶ '{keyword}' from {source_name}...")
            try:
                results = with_retry(scraper_fn, keyword, session)
                if results:
                    all_jobs.extend(results)
            except Exception as e:
                logger.error(f"[{source_name}] Error for '{keyword}': {e}")
            polite_sleep()

    logger.info(f"Total raw jobs collected: {len(all_jobs)}")
    return all_jobs
