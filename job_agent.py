#!/usr/bin/env python3
"""
Daily Job Digest — job_agent.py  (v3)
Searches for senior executive roles (MD, VP, EVP, SVP) in AI, IT Outsourcing,
Managed Services, Cloud, and Technology Consulting and emails a digest.

Job sources (all free, no API key required):
  - Arbeitnow  (public free API)
  - Remotive    (public free API)
  - RemoteOK    (public free JSON)
  - The Muse    (public free API)

Email delivery: SendGrid API (free tier = 100 emails/day)

Required GitHub Secrets:
  EMAIL_TO          — recipient address
  SENDGRID_API_KEY  — from app.sendgrid.com (free account)
  GMAIL_USER        — used as the "from" address (no password needed)
"""

import os
import json
import datetime
import hashlib
import time
from urllib.request import urlopen, Request
from urllib.parse import quote_plus
from urllib.error import URLError
import urllib.request

# ── Configuration ─────────────────────────────────────────────────────────────

EMAIL_TO         = os.environ["EMAIL_TO"]
SENDGRID_API_KEY = os.environ["SENDGRID_API_KEY"]
FROM_EMAIL       = os.environ.get("GMAIL_USER", "bartelswindy@gmail.com")

SEEN_FILE = "seen_jobs.json"

TITLE_KEYWORDS = [
    "managing director",
    "vice president",
    " vp ",
    "vp,",
    "vp-",
    "(vp)",
    "evp",
    "svp",
    "executive vice president",
    "senior vice president",
]

RELEVANT_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning",
    "managed services", "outsourcing", "cloud", "digital transformation",
    "technology consulting", "platform", "gsi", "governance",
    "portfolio", "enterprise", "saas", "it services", "cybersecurity",
    "cyber", "automation", "data", "analytics", "strategic",
]

MUSE_QUERIES = [
    "Managing Director Technology",
    "Vice President AI",
    "Vice President Managed Services",
    "Vice President Technology Consulting",
    "SVP Technology",
    "EVP Technology",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE) as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)


def job_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def fetch_url(url: str, retries: int = 3) -> bytes:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept": "application/json, */*",
    }
    req = Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=20) as r:
                return r.read()
        except URLError as e:
            print(f"  Fetch attempt {attempt+1} failed for {url[:80]}: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return b""


def title_is_senior(title: str) -> bool:
    t = " " + title.lower() + " "
    return any(kw in t for kw in TITLE_KEYWORDS)


def relevance_score(title: str, snippet: str) -> int:
    text = (title + " " + snippet).lower()
    return sum(1 for kw in RELEVANT_KEYWORDS if kw in text)


# ── Job Sources ───────────────────────────────────────────────────────────────

def fetch_arbeitnow() -> list:
    jobs = []
    url = "https://www.arbeitnow.com/api/job-board-api"
    raw = fetch_url(url)
    if not raw:
        return jobs
    try:
        data = json.loads(raw)
        for item in data.get("data", []):
            title    = (item.get("title")        or "").strip()
            company  = (item.get("company_name") or "").strip()
            location = (item.get("location")     or "Remote").strip()
            link     = (item.get("url")          or "").strip()
            desc     = (item.get("description")  or "")[:300]
            tags     = " ".join(item.get("tags", []))
            if title and link and title_is_senior(title):
                jobs.append({"title": title, "company": company, "location": location,
                             "url": link, "snippet": desc, "source": "Arbeitnow",
                             "date": item.get("created_at", ""),
                             "score": relevance_score(title, desc + " " + tags)})
    except Exception as e:
        print(f"  Arbeitnow error: {e}")
    return jobs


def fetch_remotive() -> list:
    jobs = []
    for cat in ["software-dev", "management-finance", "all-others"]:
        url = f"https://remotive.com/api/remote-jobs?category={cat}&limit=100"
        raw = fetch_url(url)
        if not raw:
            continue
        try:
            data = json.loads(raw)
            for item in data.get("jobs", []):
                title    = (item.get("title")        or "").strip()
                company  = (item.get("company_name") or "").strip()
                location = (item.get("candidate_required_location") or "Remote").strip()
                link     = (item.get("url")          or "").strip()
                desc     = (item.get("description")  or "")[:300]
                if title and link and title_is_senior(title):
                    jobs.append({"title": title, "company": company, "location": location,
                                 "url": link, "snippet": desc, "source": "Remotive",
                                 "date": item.get("publication_date", ""),
                                 "score": relevance_score(title, desc)})
        except Exception as e:
            print(f"  Remotive error ({cat}): {e}")
        time.sleep(1)
    return jobs


def fetch_remoteok() -> list:
    jobs = []
    url = "https://remoteok.com/api"
    raw = fetch_url(url)
    if not raw:
        return jobs
    try:
        data = json.loads(raw)
        for item in data:
            if not isinstance(item, dict):
                continue
            title   = (item.get("position") or "").strip()
            company = (item.get("company")  or "").strip()
            link    = (item.get("url")      or "").strip()
            desc    = (item.get("description") or "")[:300]
            tags    = " ".join(item.get("tags", []) or [])
            if title and link and title_is_senior(title):
                jobs.append({"title": title, "company": company, "location": "Remote",
                             "url": link, "snippet": desc, "source": "RemoteOK",
                             "date": str(item.get("date", "")),
                             "score": relevance_score(title, desc + " " + tags)})
    except Exception as e:
        print(f"  RemoteOK error: {e}")
    return jobs


def fetch_the_muse() -> list:
    jobs = []
    for query in MUSE_QUERIES:
        q = quote_plus(query)
        url = f"https://www.themuse.com/api/public/jobs?descending=true&page=1&query={q}"
        raw = fetch_url(url)
        if not raw:
            continue
        try:
            data = json.loads(raw)
            for item in data.get("results", []):
                title   = (item.get("name") or "").strip()
                company = (item.get("company", {}) or {}).get("name", "").strip()
                locs    = item.get("locations", []) or []
                location = ", ".join(loc.get("name", "") for loc in locs) or "US"
                link    = (item.get("refs", {}) or {}).get("landing_page", "").strip()
                if title and link and title_is_senior(title):
                    jobs.append({"title": title, "company": company, "location": location,
                                 "url": link, "snippet": "", "source": "The Muse",
                                 "date": item.get("publication_date", ""),
                                 "score": relevance_score(title, "")})
        except Exception as e:
            print(f"  The Muse error ({query}): {e}")
        time.sleep(1)
    return jobs


# ── Email via SendGrid API ────────────────────────────────────────────────────

def build_html(jobs: list) -> str:
    today = datetime.date.today().strftime("%B %d, %Y")
    rows = ""
    for j in jobs:
        if j["score"] >= 3:
            badge = (' <span style="background:#1a7f37;color:#fff;padding:2px 7px;'
                     'border-radius:10px;font-size:11px;">Strong Match</span>')
        elif j["score"] >= 1:
            badge = (' <span style="background:#9a6700;color:#fff;padding:2px 7px;'
                     'border-radius:10px;font-size:11px;">Relevant</span>')
        else:
            badge = ""

        snippet_html = (f'<div style="font-size:13px;color:#374151;margin-top:8px;">'
                        f'{j["snippet"][:200]}</div>') if j.get("snippet") else ""

        rows += f"""
        <tr>
          <td style="padding:16px;border-bottom:1px solid #e5e7eb;vertical-align:top;">
            <div style="font-size:16px;font-weight:600;">
              <a href="{j['url']}" style="color:#2563eb;text-decoration:none;">{j['title']}</a>{badge}
            </div>
            <div style="font-size:13px;color:#6b7280;margin-top:4px;">
              {j.get('company','') or '&nbsp;'}
              {(' &bull; ' + j['location']) if j.get('location') else ''}
              {(' &bull; ' + j['source']) if j.get('source') else ''}
            </div>
            {snippet_html}
          </td>
        </tr>"""

    no_jobs = ('<tr><td style="padding:32px;color:#6b7280;text-align:center;">'
               'No new matching roles today. Check back tomorrow!</td></tr>') if not rows else ""

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:30px 0;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0"
  style="background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);">
  <tr>
    <td style="background:linear-gradient(135deg,#1e3a5f,#2563eb);padding:30px 32px;">
      <div style="color:#fff;font-size:22px;font-weight:700;">&#128188; Daily Job Digest</div>
      <div style="color:#bfdbfe;font-size:13px;margin-top:4px;">
        {today} &bull; MD / VP / EVP / SVP &bull; AI &bull; Technology &bull; Managed Services
      </div>
    </td>
  </tr>
  <tr>
    <td style="background:#eff6ff;padding:12px 32px;border-bottom:1px solid #dbeafe;">
      <span style="font-size:13px;color:#1e40af;">
        &#10003; <strong>{len(jobs)} new role{'s' if len(jobs) != 1 else ''}</strong> found today
      </span>
    </td>
  </tr>
  <table width="100%" cellpadding="0" cellspacing="0">
    {rows}{no_jobs}
  </table>
  <tr>
    <td style="padding:20px 32px;border-top:1px solid #e5e7eb;background:#f9fafb;">
      <div style="font-size:11px;color:#9ca3af;">
        Digest for Windy Bartels &bull; MD / VP / EVP / SVP &bull;
        AI / IT Outsourcing / Managed Services / Cloud / Technology Consulting &bull;
        Open to Relocation
      </div>
    </td>
  </tr>
</table>
</td></tr>
</table>
</body></html>"""


def send_email(html: str, job_count: int):
    subject = (f"[Job Digest] {job_count} New Senior "
               f"Role{'s' if job_count != 1 else ''} — {datetime.date.today()}")

    payload = json.dumps({
        "personalizations": [{"to": [{"email": EMAIL_TO}]}],
        "from": {"email": FROM_EMAIL, "name": "Daily Job Digest"},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}]
    }).encode("utf-8")

    req = Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=payload,
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST"
    )

    with urlopen(req, timeout=30) as resp:
        status = resp.status
    print(f"SendGrid response: HTTP {status}")
    if status not in (200, 202):
        raise RuntimeError(f"SendGrid returned HTTP {status}")
    print(f"Email sent: '{subject}'")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Daily Job Digest v3 — {datetime.datetime.utcnow().isoformat()}Z")
    seen = load_seen()
    all_jobs = []

    print("\nFetching from Arbeitnow...")
    all_jobs.extend(fetch_arbeitnow())
    print(f"  {len(all_jobs)} senior roles so far")

    print("\nFetching from Remotive...")
    before = len(all_jobs)
    all_jobs.extend(fetch_remotive())
    print(f"  +{len(all_jobs) - before} roles")

    print("\nFetching from RemoteOK...")
    before = len(all_jobs)
    all_jobs.extend(fetch_remoteok())
    print(f"  +{len(all_jobs) - before} roles")

    print("\nFetching from The Muse...")
    before = len(all_jobs)
    all_jobs.extend(fetch_the_muse())
    print(f"  +{len(all_jobs) - before} roles")

    # Deduplicate
    new_jobs, new_ids = [], set()
    for job in all_jobs:
        jid = job_id(job["url"])
        if jid not in seen and jid not in new_ids:
            new_jobs.append(job)
            new_ids.add(jid)

    new_jobs.sort(key=lambda j: -j["score"])
    print(f"\nTotal fetched: {len(all_jobs)} | New (unseen): {len(new_jobs)}")

    send_email(build_html(new_jobs), len(new_jobs))

    seen.update(new_ids)
    save_seen(seen)
    print("seen_jobs.json updated.")


if __name__ == "__main__":
    main()
