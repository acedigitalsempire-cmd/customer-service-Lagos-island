"""
Parser module — converts filtered job dicts into structured output formats.
"""
from datetime import datetime, timezone
from typing import List, Dict


def jobs_to_table_rows(jobs: List[Dict]) -> List[Dict]:
    """Return jobs as clean display rows for email/CSV."""
    rows = []
    for job in jobs:
        rows.append({
            "Job Title": job.get("title", "N/A"),
            "Company": job.get("company", "N/A"),
            "Location": job.get("location", "N/A"),
            "Salary": job.get("salary", "Not Disclosed"),
            "Date Posted": job.get("date_display", "N/A"),
            "Deadline": job.get("deadline", "Not Specified"),
            "Source": job.get("source", "N/A"),
            "Apply Link": job.get("link", "#"),
            "High Paying": job.get("high_paying", False),
        })
    return rows


def jobs_to_csv(jobs: List[Dict]) -> str:
    """Generate CSV string from job list."""
    import csv
    import io
    rows = jobs_to_table_rows(jobs)
    if not rows:
        return ""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def build_report(jobs: List[Dict]) -> Dict:
    """Build a structured report object."""
    today = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
    return {
        "date": today,
        "total": len(jobs),
        "rows": jobs_to_table_rows(jobs),
        "high_paying_count": sum(1 for j in jobs if j.get("high_paying")),
        "sources": list(set(j.get("source", "") for j in jobs)),
    }
