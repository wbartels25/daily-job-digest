#!/usr/bin/env python3
"""
Daily Job Digest — job_agent.py
Searches for senior executive roles (MD, VP, EVP, SVP) in AI, IT Outsourcing,
Managed Services, Cloud, and Technology Consulting and emails a digest to GMAIL_USER.

Required GitHub Secrets:
  EMAIL_TO            — recipient address
  GMAIL_USER          — sender Gmail address
  GMAIL_APP_PASSWORD  — Gmail App Password (not your regular password)
"""

import os
import json
import smtplib
import datetime
import hashlib
import time
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.request import urlopen, Request
from urllib.parse import urlencode, quote_plus
from urllib.error import URLError

# ── Configuration ─────────────────────────────────────────────────────────────

EMAIL_TO           = os.environ["EMAIL_TO"]
GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]

SEEN_FILE = "seen_jobs.json"

# Titles Windy is targeting
TITLE_QUERIES = [
    "Managing Director AI",
    "Managing Director IT Outsourcing",
    "Managing Director Managed Services",
    "Managing Director Technology Consulting",
    "VP AI Platform",
    "VP Managed Services",
    "VP IT Outsourcing",
    "VP Cloud Technology",
    "EVP Technology",
    "EVP AI",
    "SVP Technology",
    "SVP AI",
    "SVP Managed Services",
    "Executive Vice President Technology",
    "Executive Vice President AI",
    "Senior Vice President AI Outsourcing",
]

# Keywords that must appear in title or snippet (at least one)
MUST_INCLUDE = [
    "managing director", "vice president", " vp ", "evp", "svp",
    "executive vice president", "senior vice president",
]

# Keywords that boost relevance — used for ordering/filtering
RELEVANT_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "ml",
    "managed services", "outsourcing", "cloud", "digital transformation",
    "technology consulting", "platform", "gsi", "capgemini", "atos",
    "accenture", "infosys", "tcs", "cognizant", "wipro", "deloitte",
    "governance", "portfolio", "enterprise", "saas", "it services",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)


def job_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def fetch_url(url: str, retries: int = 3) -> bytes:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; JobDigestBot/1.0)"}
    req = Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=15) as r:
                return r.read()
        except URLError as e:
            if attempt == retries - 1:
                print(f"  ⚠ Failed to fetch {url}: {e}")
                return b""
            time.sleep(2 ** attempt)
    return b""


def title_is_senior(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in MUST_INCLUDE)


def relevance_score(title: str, snippet: str) -> int:
    text = (title + " " + snippet).lower()
    return sum(1 for kw in RELEVANT_KEYWORDS if kw in text)


# ── Job Sources ───────────────────────────────────────────────────────────────

def fetch_indeed_rss(query: str) -> list[dict]:
    """Pull jobs from Indeed RSS (no API key needed)."""
    jobs = []
    params = urlencode({
        "q": query,
        "l": "",          # blank = nationwide
        "sort": "date",
        "limit": 25,
    })
    url = f"https://www.indeed.com/rss?{params}"
    raw = fetch_url(url)
    if not raw:
        return jobs
    try:
        root = ET.fromstring(raw)
        ns = ""
        for item in root.findall(f".//item"):
            title   = (item.findtext("title") or "").strip()
            link    = (item.findtext("link")  or "").strip()
            desc    = (item.findtext("description") or "").strip()
            company = (item.findtext("{https://www.indeed.com/about/}employer") or
                       item.findtext("author") or "").strip()
            location = (item.findtext("{https://www.indeed.com/about/}city") or
                        item.findtext("{https://www.indeed.com/about/}state") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()

            if title and link and title_is_senior(title):
                jobs.append({
                    "title":    title,
                    "company":  company,
                    "location": location,
                    "url":      link,
                    "snippet":  desc[:300],
                    "source":   "Indeed",
                    "date":     pub_date,
                    "score":    relevance_score(title, desc),
                })
    except ET.ParseError as e:
        print(f"  ⚠ XML parse error for Indeed query '{query}': {e}")
    return jobs


def fetch_remoteok() -> list[dict]:
    """Pull senior remote tech jobs from RemoteOK (free JSON API)."""
    jobs = []
    url = "https://remoteok.com/api?tag=executive"
    raw = fetch_url(url)
    if not raw:
        return jobs
    try:
        data = json.loads(raw)
        for item in data:
            if not isinstance(item, dict):
                continue
            title    = (item.get("position") or "").strip()
            company  = (item.get("company")  or "").strip()
            location = (item.get("location") or "Remote").strip()
            link     = (item.get("url")      or item.get("apply_url") or "").strip()
            desc     = (item.get("description") or "").strip()
            date     = item.get("date", "")

            if title and link and title_is_senior(title):
                jobs.append({
                    "title":    title,
                    "company":  company,
                    "location": location,
                    "url":      link,
                    "snippet":  desc[:300],
                    "source":   "RemoteOK",
                    "date":     str(date),
                    "score":    relevance_score(title, desc),
                })
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  ⚠ RemoteOK parse error: {e}")
    return jobs


def fetch_jobicy() -> list[dict]:
    """Pull senior jobs from Jobicy free API."""
    jobs = []
    for tag in ["technology", "ai", "management"]:
        url = f"https://jobicy.com/api/v2/remote-jobs?count=50&industry={tag}"
        raw = fetch_url(url)
        if not raw:
            continue
        try:
            data = json.loads(raw)
            for item in data.get("jobs", []):
                title    = (item.get("jobTitle")    or "").strip()
                company  = (item.get("companyName") or "").strip()
                location = (item.get("jobGeo")      or "Remote").strip()
                link     = (item.get("url")         or "").strip()
                desc     = (item.get("jobExcerpt")  or "").strip()
                date     = item.get("pubDate", "")

                if title and link and title_is_senior(title):
                    jobs.append({
                        "title":    title,
                        "company":  company,
                        "location": location,
                        "url":      link,
                        "snippet":  desc[:300],
                        "source":   "Jobicy",
                        "date":     str(date),
                        "score":    relevance_score(title, desc),
                    })
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  ⚠ Jobicy parse error ({tag}): {e}")
        time.sleep(1)
    return jobs


def fetch_adzuna(query: str) -> list[dict]:
    """Adzuna has a free public search — no key needed for basic RSS."""
    jobs = []
    q = quote_plus(query)
    url = f"https://api.adzuna.com/v1/api/jobs/us/search/1?app_id=&app_key=&results_per_page=20&what={q}&content-type=application/json"
    # Adzuna requires keys; skip silently — included for future use
    return jobs


# ── Email ─────────────────────────────────────────────────────────────────────

def build_html(jobs: list[dict]) -> str:
    today = datetime.date.today().strftime("%B %d, %Y")
    rows = ""
    for j in jobs:
        score_badge = ""
        if j["score"] >= 3:
            score_badge = ' <span style="background:#1a7f37;color:#fff;padding:2px 7px;border-radius:10px;font-size:11px;">Strong Match</span>'
        elif j["score"] >= 1:
            score_badge = ' <span style="background:#9a6700;color:#fff;padding:2px 7px;border-radius:10px;font-size:11px;">Relevant</span>'

        rows += f"""
        <tr>
          <td style="padding:16px;border-bottom:1px solid #e5e7eb;vertical-align:top;">
            <div style="font-size:16px;font-weight:600;color:#111827;">
              <a href="{j['url']}" style="color:#2563eb;text-decoration:none;">{j['title']}</a>{score_badge}
            </div>
            <div style="font-size:13px;color:#6b7280;margin-top:4px;">
              {j.get('company','') or '&nbsp;'}
              {(' &bull; ' + j['location']) if j.get('location') else ''}
              {(' &bull; ' + j['source']) if j.get('source') else ''}
            </div>
            <div style="font-size:13px;color:#374151;margin-top:8px;">{j.get('snippet','')}</div>
          </td>
        </tr>"""

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:30px 0;">
    <tr><td align="center">
      <table width="640" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);">

        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#1e3a5f,#2563eb);padding:30px 32px;">
            <div style="color:#fff;font-size:22px;font-weight:700;">&#128188; Daily Job Digest</div>
            <div style="color:#bfdbfe;font-size:13px;margin-top:4px;">{today} &bull; MD / VP / EVP / SVP &bull; AI &bull; Technology &bull; Managed Services</div>
          </td>
        </tr>

        <!-- Summary bar -->
        <tr>
          <td style="background:#eff6ff;padding:12px 32px;border-bottom:1px solid #dbeafe;">
            <span style="font-size:13px;color:#1e40af;">
              &#10003; <strong>{len(jobs)} new role{'s' if len(jobs) != 1 else ''}</strong> found today matching your profile
            </span>
          </td>
        </tr>

        <!-- Jobs -->
        <table width="100%" cellpadding="0" cellspacing="0">
          {rows if rows else '<tr><td style="padding:32px;color:#6b7280;text-align:center;">No new matching roles today. Check back tomorrow!</td></tr>'}
        </table>

        <!-- Footer -->
        <tr>
          <td style="padding:20px 32px;border-top:1px solid #e5e7eb;background:#f9fafb;">
            <div style="font-size:11px;color:#9ca3af;">
              Automated digest for Windy Bartels &bull; Roles: MD, VP, EVP, SVP &bull;
              Industries: AI, IT Outsourcing, Managed Services, Cloud, Technology Consulting &bull;
              Location: Open to Relocation
            </div>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_email(html: str, job_count: int):
    subject = f"[Job Digest] {job_count} New Senior Role{'s' if job_count != 1 else ''} — {datetime.date.today()}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, EMAIL_TO, msg.as_string())
    print(f"✅ Email sent: '{subject}'")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"🔍 Daily Job Digest starting — {datetime.datetime.utcnow().isoformat()}Z")
    seen = load_seen()
    all_jobs: list[dict] = []

    # Indeed RSS — one query per search term
    print("\nFetching from Indeed RSS...")
    for query in TITLE_QUERIES:
        print(f"  → {query}")
        jobs = fetch_indeed_rss(query)
        all_jobs.extend(jobs)
        time.sleep(1.5)   # be polite

    # RemoteOK
    print("\nFetching from RemoteOK...")
    all_jobs.extend(fetch_remoteok())

    # Jobicy
    print("\nFetching from Jobicy...")
    all_jobs.extend(fetch_jobicy())

    # Deduplicate by URL hash
    new_jobs = []
    new_ids  = set()
    for job in all_jobs:
        jid = job_id(job["url"])
        if jid not in seen and jid not in new_ids:
            new_jobs.append(job)
            new_ids.add(jid)

    # Sort: strong matches first, then by source
    new_jobs.sort(key=lambda j: -j["score"])

    print(f"\n📊 Total fetched: {len(all_jobs)} | New (unseen): {len(new_jobs)}")

    # Always send the email (even if 0 new jobs — so you know it ran)
    html = build_html(new_jobs)
    send_email(html, len(new_jobs))

    # Persist seen IDs
    seen.update(new_ids)
    save_seen(seen)
    print("💾 seen_jobs.json updated.")


if __name__ == "__main__":
    main()
