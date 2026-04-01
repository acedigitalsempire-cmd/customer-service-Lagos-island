"""
Email delivery module — sends via Resend API (https://resend.com).
Sender is always a Resend-safe address. Gmail addresses as sender are rejected
by Resend and are auto-replaced with onboarding@resend.dev.
"""
import re
import requests
from typing import List, Dict
import config
from utils import logger


# ─── Resolve a safe sender address ───────────────────────────────────────────
def _safe_from() -> str:
    """
    Resend only allows sending FROM a verified domain you own.
    Gmail / Yahoo / Hotmail etc. are NOT allowed as senders.
    If EMAIL_FROM secret is set to a free-mail address, fall back to
    Resend's shared test sender which works for any receiver.
    """
    raw = (config.EMAIL_FROM or "").strip()
    # Extract the email address portion from "Name <email>" format
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", raw)
    email = match.group(0).lower() if match else ""

    blocked_domains = ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com")
    if not email or any(email.endswith(d) for d in blocked_domains):
        logger.warning(
            f"EMAIL_FROM '{raw}' is a free-mail address — "
            "Resend doesn't allow these as senders. "
            "Falling back to onboarding@resend.dev"
        )
        return "Lagos Job Alert <onboarding@resend.dev>"
    return raw or "Lagos Job Alert <onboarding@resend.dev>"


# ─── HTML Template ────────────────────────────────────────────────────────────
def _build_html(report: Dict) -> str:
    date_str = report["date"]
    total = report["total"]
    rows: List[Dict] = report["rows"]
    high_pay = report["high_paying_count"]
    sources = ", ".join(report["sources"])

    if total == 0:
        return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Lagos Island Job Alert</title>
<style>body{{font-family:'Segoe UI',sans-serif;background:#f5f5f5;margin:0;padding:20px;}}
.card{{background:#fff;border-radius:12px;padding:40px;max-width:600px;margin:0 auto;
text-align:center;box-shadow:0 4px 16px rgba(0,0,0,.08);}}
h1{{color:#1a6b3c;}}p{{color:#555;font-size:16px;}}</style></head>
<body><div class="card"><h1>🌿 Lagos Island Job Alert</h1>
<p><strong>{date_str}</strong></p>
<p style="font-size:18px;">No new Lagos Island customer support jobs found in the last 48 hours.</p>
<p>We'll check again tomorrow. Stay ready!</p></div></body></html>"""

    row_html = ""
    for i, row in enumerate(rows):
        bg = "#fffdf0" if row["High Paying"] else ("#f9fafb" if i % 2 else "#ffffff")
        badge = (' <span style="background:#f59e0b;color:#fff;border-radius:4px;'
                 'padding:1px 6px;font-size:11px;font-weight:700;">💰 HIGH PAY</span>'
                 if row["High Paying"] else "")
        row_html += f"""
      <tr style="background:{bg};">
        <td style="padding:12px 10px;border-bottom:1px solid #e5e7eb;font-weight:600;color:#111;">
          {row['Job Title']}{badge}</td>
        <td style="padding:12px 10px;border-bottom:1px solid #e5e7eb;color:#374151;">{row['Company']}</td>
        <td style="padding:12px 10px;border-bottom:1px solid #e5e7eb;color:#374151;">📍 {row['Location']}</td>
        <td style="padding:12px 10px;border-bottom:1px solid #e5e7eb;color:#059669;font-weight:500;">{row['Salary']}</td>
        <td style="padding:12px 10px;border-bottom:1px solid #e5e7eb;color:#6b7280;font-size:13px;">{row['Date Posted']}</td>
        <td style="padding:12px 10px;border-bottom:1px solid #e5e7eb;color:#6b7280;font-size:13px;">{row['Deadline']}</td>
        <td style="padding:12px 10px;border-bottom:1px solid #e5e7eb;font-size:12px;color:#6b7280;">{row['Source']}</td>
        <td style="padding:12px 10px;border-bottom:1px solid #e5e7eb;text-align:center;">
          <a href="{row['Apply Link']}"
             style="background:#1a6b3c;color:#fff;padding:7px 14px;border-radius:6px;
                    text-decoration:none;font-size:13px;font-weight:600;white-space:nowrap;">
            Apply →</a></td>
      </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Daily Lagos Island Customer Support Jobs – {date_str}</title></head>
<body style="margin:0;padding:0;background:#f0f4f0;font-family:'Segoe UI',Arial,sans-serif;">

  <div style="background:linear-gradient(135deg,#1a6b3c 0%,#0f4a28 100%);padding:36px 24px;text-align:center;">
    <h1 style="color:#fff;margin:0;font-size:26px;">🏙️ Lagos Island Customer Support Jobs</h1>
    <p style="color:#a7f3c8;margin:8px 0 0;font-size:15px;">{date_str}</p>
  </div>

  <div style="background:#fff;border-bottom:3px solid #1a6b3c;padding:16px 24px;text-align:center;">
    <span style="margin:0 16px;font-size:15px;color:#111;">
      <strong style="font-size:22px;color:#1a6b3c;">{total}</strong> jobs found</span>
    <span style="margin:0 16px;font-size:15px;color:#111;">
      <strong style="font-size:22px;color:#f59e0b;">{high_pay}</strong> high-paying</span>
    <span style="margin:0 16px;font-size:13px;color:#6b7280;">Sources: {sources}</span>
  </div>

  <div style="padding:14px 24px;background:#ecfdf5;border-bottom:1px solid #d1fae5;font-size:13px;color:#065f46;">
    ✅ Lagos Island only &nbsp;|&nbsp; ✅ Last 48 hours &nbsp;|&nbsp; ✅ Newest first
  </div>

  <div style="padding:24px;overflow-x:auto;">
    <table style="width:100%;border-collapse:collapse;background:#fff;border-radius:10px;
                  overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.07);font-size:14px;">
      <thead>
        <tr style="background:#1a6b3c;color:#fff;">
          <th style="padding:14px 10px;text-align:left;">Job Title</th>
          <th style="padding:14px 10px;text-align:left;">Company</th>
          <th style="padding:14px 10px;text-align:left;">Location</th>
          <th style="padding:14px 10px;text-align:left;">Salary</th>
          <th style="padding:14px 10px;text-align:left;">Date Posted</th>
          <th style="padding:14px 10px;text-align:left;">Deadline</th>
          <th style="padding:14px 10px;text-align:left;">Source</th>
          <th style="padding:14px 10px;text-align:center;">Apply</th>
        </tr>
      </thead>
      <tbody>{row_html}</tbody>
    </table>
  </div>

  <div style="padding:24px;text-align:center;font-size:12px;color:#9ca3af;">
    <p>Covers: Lekki · Victoria Island · Ikoyi · Ajah · Sangotedo · Chevron · Lagos Island</p>
    <p>Automated Lagos Island Job Alert · Last 48 hours only</p>
  </div>
</body></html>"""


# ─── Plain text fallback ──────────────────────────────────────────────────────
def _build_text(report: Dict) -> str:
    date_str = report["date"]
    total = report["total"]
    rows = report["rows"]
    if total == 0:
        return (f"Lagos Island Job Alert — {date_str}\n"
                "No new customer support jobs found in last 48 hours.")
    lines = [f"LAGOS ISLAND CUSTOMER SUPPORT JOBS — {date_str}",
             f"Total: {total}", "=" * 70]
    for i, row in enumerate(rows, 1):
        hp = " [HIGH PAY]" if row["High Paying"] else ""
        lines += [f"\n{i}. {row['Job Title']}{hp}",
                  f"   Company  : {row['Company']}",
                  f"   Location : {row['Location']}",
                  f"   Salary   : {row['Salary']}",
                  f"   Posted   : {row['Date Posted']}",
                  f"   Deadline : {row['Deadline']}",
                  f"   Source   : {row['Source']}",
                  f"   Apply    : {row['Apply Link']}"]
    return "\n".join(lines)


# ─── Send via Resend API ──────────────────────────────────────────────────────
def send_email(report: Dict) -> bool:
    if not config.RESEND_API_KEY:
        logger.error("RESEND_API_KEY missing.")
        return False
    if not config.RECEIVER_EMAIL:
        logger.error("RECEIVER_EMAIL missing.")
        return False

    date_str = report["date"]
    subject = f"Daily Lagos Island Customer Support Jobs – {date_str}"
    sender = _safe_from()
    logger.info(f"Sending from: {sender} → {config.RECEIVER_EMAIL}")

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {config.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": sender,
                "to": [config.RECEIVER_EMAIL],
                "subject": subject,
                "html": _build_html(report),
                "text": _build_text(report),
            },
            timeout=30,
        )
        if resp.status_code == 200:
            logger.info(f"✅ Email sent | id={resp.json().get('id')} | to={config.RECEIVER_EMAIL}")
            return True
        else:
            logger.error(f"Resend API error {resp.status_code}: {resp.text}")
            return False
    except requests.exceptions.Timeout:
        logger.error("Resend request timed out.")
    except Exception as e:
        logger.error(f"Email error: {e}")
    return False
