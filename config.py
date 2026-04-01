"""
Configuration file for Lagos Island Customer Support Job Alert System
"""
import os

# ─── Email Configuration (Resend) ───────────────────────────────────────────
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
# Resend requires a verified sender domain. Use your verified "from" address here.
# e.g. "Lagos Jobs <alerts@yourdomain.com>"
EMAIL_FROM = os.environ.get("EMAIL_FROM", "Lagos Job Alert <onboarding@resend.dev>")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL", "jobhauntgithub@gmail.com")

# ─── Job Search Keywords ────────────────────────────────────────────────────
SEARCH_KEYWORDS = [
    "Customer Service Representative",
    "Customer Support",
    "Customer Care",
    "Support Officer",
]

# ─── Allowed Lagos Island Locations ─────────────────────────────────────────
ALLOWED_LOCATIONS = [
    "lekki",
    "victoria island",
    "vi",
    "ikoyi",
    "ajah",
    "sangotedo",
    "chevron",
    "lagos island",
    "eti-osa",
    "eti osa",
    "oniru",
    "osapa",
    "agungi",
    "ikate",
    "jakande",
    "lafiaji",
    "admiralty",
]

# ─── Excluded Mainland Locations ────────────────────────────────────────────
EXCLUDED_LOCATIONS = [
    "yaba",
    "surulere",
    "ikeja",
    "maryland",
    "ojota",
    "ketu",
    "gbagada",
    "mushin",
    "oshodi",
    "agege",
    "ikorodu",
    "alimosho",
    "isolo",
    "kosofe",
    "shomolu",
    "somolu",
    "bariga",
    "mainland",
    "festac",
    "amuwo",
    "ilupeju",
    "oregun",
    "ogba",
    "berger",
    "ojodu",
]

# ─── Job Sources ─────────────────────────────────────────────────────────────
JOB_SOURCES = {
    "jobberman": {
        "base_url": "https://www.jobberman.com",
        "search_url": "https://www.jobberman.com/jobs?q={keyword}&l=Lagos",
        "enabled": True,
    },
    "myjobmag": {
        "base_url": "https://www.myjobmag.com",
        "search_url": "https://www.myjobmag.com/jobs/search?query={keyword}&location=Lagos",
        "enabled": True,
    },
    "hotnigerianjobs": {
        "base_url": "https://www.hotnigerianjobs.com",
        "search_url": "https://www.hotnigerianjobs.com/?s={keyword}",
        "enabled": True,
    },
    "indeed": {
        "base_url": "https://ng.indeed.com",
        "search_url": "https://ng.indeed.com/jobs?q={keyword}&l=Lagos+Island",
        "enabled": True,
    },
    "linkedin": {
        "base_url": "https://www.linkedin.com",
        "search_url": "https://www.linkedin.com/jobs/search/?keywords={keyword}&location=Lagos%20Island%2C%20Nigeria",
        "enabled": True,
    },
}

# ─── Scraping Settings ───────────────────────────────────────────────────────
REQUEST_TIMEOUT = 30          # seconds
MAX_RETRIES = 3
RETRY_DELAY = 5               # seconds between retries
MAX_JOBS_PER_SOURCE = 50
HOURS_LIMIT = 48              # only jobs posted within 48 hours

# ─── Request Headers (rotate to avoid blocks) ────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

# ─── Logging ────────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"
LOG_FILE = "job_alert.log"
