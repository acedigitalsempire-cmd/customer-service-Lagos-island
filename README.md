# 🏙️ Lagos Island Customer Support Job Alert System

An automated daily job alert system that scrapes Nigerian job platforms and emails you **only** Customer Support / Service roles posted within the last 48 hours in **Lagos Island areas** (Lekki, Victoria Island, Ikoyi, Ajah, Sangotedo, Chevron).

---

## 📁 Project Structure

```
lagos-job-alert/
├── .github/
│   └── workflows/
│       └── daily.yml        ← GitHub Actions (runs 8 AM Nigeria time)
├── main.py                  ← Entry point
├── job_scraper.py           ← Scrapes Jobberman, MyJobMag, Indeed, LinkedIn, HotNigerianJobs
├── filter.py                ← Strict location + date filtering
├── parser.py                ← Formats jobs into table / CSV
├── emailer.py               ← Sends rich HTML email
├── utils.py                 ← Shared helpers (date parsing, dedup, validation)
├── config.py                ← All settings in one place
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup (5 minutes)

### 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/lagos-job-alert.git
cd lagos-job-alert
pip install -r requirements.txt
```

### 2. Set environment variables (local testing)

```bash
export EMAIL_USER="yourgmail@gmail.com"
export EMAIL_PASS="your_app_password"       # Gmail App Password (not your login password)
export RECEIVER_EMAIL="recipient@email.com"
```

> **Gmail App Password:** Go to Google Account → Security → 2-Step Verification → App passwords → Generate one for "Mail".

### 3. Run manually

```bash
python main.py
```

---

## 🔐 GitHub Secrets Setup

In your GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret Name      | Value                          |
|-----------------|--------------------------------|
| `EMAIL_USER`    | your Gmail address             |
| `EMAIL_PASS`    | your Gmail App Password        |
| `RECEIVER_EMAIL`| email to receive job alerts    |

---

## ⏰ Schedule

- Runs **daily at 7:00 AM UTC = 8:00 AM Nigeria Time (WAT)**
- Can also be triggered manually from GitHub Actions tab → "Run workflow"

---

## 🔍 What Gets Filtered In

| Criterion | Rule |
|-----------|------|
| **Location** | Lekki, Victoria Island, Ikoyi, Ajah, Sangotedo, Chevron, Lagos Island only |
| **Time** | Posted within last **48 hours** only |
| **Keywords** | Customer Service Rep, Customer Support, Customer Care, Support Officer |
| **Sources** | Jobberman, MyJobMag, HotNigerianJobs, Indeed Nigeria, LinkedIn |

## ❌ What Gets Excluded

- Yaba, Surulere, Ikeja, and any mainland location
- Jobs older than 48 hours
- Jobs with no posting date
- Remote roles (location-based filtering removes non-Lagos entries)
- Duplicate listings

---

## 📧 Email Format

**Subject:** `Daily Lagos Island Customer Support Jobs – Wednesday, 01 January 2025`

**Body includes:**
- Total jobs found
- High-paying job count (≥ ₦200,000/month flagged with 💰)
- Full table: Title · Company · Location · Salary · Date · Deadline · Source · Apply button
- Empty alert if no jobs found

---

## 🛠️ Customisation

### Add more locations (config.py)
```python
ALLOWED_LOCATIONS = [..., "your_new_area"]
```

### Change email schedule (daily.yml)
```yaml
- cron: "0 7 * * *"   # UTC — change hour to shift Nigeria time
```

### Disable a source
```python
JOB_SOURCES = {
    "linkedin": {"enabled": False},  # turn off LinkedIn
}
```

### High-paying threshold
Edit `filter.py` → `int(a) >= 200000` (change 200000 to your threshold in Naira).

---

## 🐛 Error Handling

| Situation | Behaviour |
|-----------|-----------|
| No jobs found | Email sent: "No new jobs in last 48 hours" |
| Website structure change | Source skipped, others continue |
| Timeout | 3 automatic retries with backoff |
| Missing date | Job silently skipped |
| Missing salary | Marked "Not Disclosed" |
| Invalid link | Job skipped |
| Email auth failure | Logged; exit code 1 triggers GitHub Actions failure |

---

## 📊 Audit Trail

Each run saves a `jobs_YYYYMMDD.csv` file which is uploaded as a GitHub Actions artifact (kept 7 days) so you can review what was found even without opening your email.

---

## 🚀 Optional Enhancements

- **Google Sheets:** Add `gspread` and append rows to a sheet each run
- **Telegram:** Use `python-telegram-bot` and send the table to a channel
- **WhatsApp:** Use Twilio's WhatsApp API
- **Slack:** Use `slack-sdk` WebhookClient

---

## 📄 License

MIT — free to use and modify.
