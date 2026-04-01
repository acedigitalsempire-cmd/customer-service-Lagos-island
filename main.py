"""
Main entry point for Lagos Island Customer Support Job Alert System.
Run: python main.py
"""
import sys
from utils import logger
from job_scraper import scrape_all_sources
from filter import filter_jobs
from parser import build_report, jobs_to_csv
from emailer import send_email


def main():
    logger.info("=" * 60)
    logger.info("Lagos Island Job Alert System — Starting")
    logger.info("=" * 60)

    # 1. Scrape all sources
    logger.info("Step 1/4 — Scraping job platforms...")
    raw_jobs = scrape_all_sources()

    if not raw_jobs:
        logger.warning("No raw jobs collected from any source.")

    # 2. Filter
    logger.info("Step 2/4 — Applying filters...")
    filtered = filter_jobs(raw_jobs)
    logger.info(f"Filtered jobs ready: {len(filtered)}")

    # 3. Build report
    logger.info("Step 3/4 — Building report...")
    report = build_report(filtered)

    # Save CSV for audit trail
    csv_data = jobs_to_csv(filtered)
    if csv_data:
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y%m%d")
        fname = f"jobs_{ts}.csv"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(csv_data)
        logger.info(f"CSV saved: {fname}")

    # 4. Send email
    logger.info("Step 4/4 — Sending email...")
    success = send_email(report)

    if success:
        logger.info("✅ Job alert cycle complete.")
        sys.exit(0)
    else:
        logger.error("❌ Email sending failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
