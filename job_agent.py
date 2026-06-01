#!/usr/bin/env python3
"""
Daily Job Digest v5 - Outlook SMTP edition
Senior exec roles: MD, VP, EVP, SVP
Industries: AI, IT Outsourcing, Managed Services, Cloud, Technology Consulting

Required GitHub Secrets:
  EMAIL_TO      - recipient address (bartelswindy@gmail.com)
  SMTP_USER     - windy@hiveadvisorygroup.com
  SMTP_PASSWORD - Outlook password for hiveadvisorygroup.com
"""

import os, json, datetime, hashlib, time, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.request import urlopen, Request
from urllib.parse import quote_plus
from urllib.error import URLError

EMAIL_TO      = os.environ["EMAIL_TO"]
SMTP_USER     = os.environ["SMTP_USER"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]
SEEN_FILE     = "seen_jobs.json"

TITLE_KEYWORDS = [
    "managing director", "vice president", " vp ", "vp,", "vp-",
    "evp", "svp", "executive vice president", "senior vice president",
]

RELEVANT_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning",
    "managed services", "outsourcing", "cloud", "digital transformation",
    "technology consulting", "platform", "gsi", "governance",
    "portfolio", "enterprise", "saas", "it services", "cybersecurity",
    "automation", "analytics", "strategic",
]

MUSE_QUERIES = [
    "Managing Director Technology", "Vice President AI",
    "Vice President Managed Services", "Vice President Technology Consulting",
    "SVP Technology", "EVP Technology",
]


def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE) as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)


def job_id(url):
    return hashlib.md5(url.encode()).hexdigest()


def fetch_url(url, retries=3):
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
        "Accept": "application/json",
    })
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=20) as r:
                return r.read()
        except URLError as e:
            print(f"  attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    return b""


def is_senior(title):
    t = " " + title.lower() + " "
    return any(kw in t for kw in TITLE_KEYWORDS)


def score(title, text):
    t = (title + " " + text).lower()
    return sum(1 for kw in RELEVANT_KEYWORDS if kw in t)


def fetch_arbeitnow():
    jobs = []
    raw = fetch_url("https://www.arbeitnow.com/api/job-board-api")
    if not raw:
        return jobs
    try:
        for item in json.loads(raw).get("data", []):
            t = (item.get("title") or "").strip()
            d = (item.get("description") or "")[:300]
            if t and item.get("url") and is_senior(t):
                jobs.append({"title": t, "company": item.get("company_name",""),
                    "location": item.get("location","Remote"), "url": item["url"],
                    "snippet": d, "source": "Arbeitnow",
                    "score": score(t, d + " ".join(item.get("tags",[])))})
    except Exception as e:
        print(f"  Arbeitnow: {e}")
    return jobs


def fetch_remotive():
    jobs = []
    for cat in ["software-dev", "management-finance", "all-others"]:
        raw = fetch_url(f"https://remotive.com/api/remote-jobs?category={cat}&limit=100")
        if not raw:
            continue
        try:
            for item in json.loads(raw).get("jobs", []):
                t = (item.get("title") or "").strip()
                d = (item.get("description") or "")[:300]
                if t and item.get("url") and is_senior(t):
                    jobs.append({"title": t, "company": item.get("company_name",""),
                        "location": item.get("candidate_required_location","Remote"),
                        "url": item["url"], "snippet": d, "source": "Remotive",
                        "score": score(t, d)})
        except Exception as e:
            print(f"  Remotive {cat}: {e}")
        time.sleep(1)
    return jobs


def fetch_remoteok():
    jobs = []
    raw = fetch_url("https://remoteok.com/api")
    if not raw:
        return jobs
    try:
        for item in json.loads(raw):
            if not isinstance(item, dict):
                continue
            t = (item.get("position") or "").strip()
            d = (item.get("description") or "")[:300]
            if t and item.get("url") and is_senior(t):
                jobs.append({"title": t, "company": item.get("company",""),
                    "location": "Remote", "url": item["url"],
                    "snippet": d, "source": "RemoteOK",
                    "score": score(t, d + " ".join(item.get("tags",[]) or []))})
    except Exception as e:
        print(f"  RemoteOK: {e}")
    return jobs


def fetch_the_muse():
    jobs = []
    for q in MUSE_QUERIES:
        raw = fetch_url(f"https://www.themuse.com/api/public/jobs?descending=true&page=1&query={quote_plus(q)}")
        if not raw:
            continue
        try:
            for item in json.loads(raw).get("results", []):
                t    = (item.get("name") or "").strip()
                link = (item.get("refs",{}) or {}).get("landing_page","").strip()
                locs = ", ".join(l.get("name","") for l in (item.get("locations",[]) or []))
                co   = (item.get("company",{}) or {}).get("name","")
                if t and link and is_senior(t):
                    jobs.append({"title": t, "company": co, "location": locs or "US",
                        "url": link, "snippet": "", "source": "The Muse",
                        "score": score(t, "")})
        except Exception as e:
            print(f"  The Muse {q}: {e}")
        time.sleep(1)
    return jobs


def build_html(jobs):
    today = datetime.date.today().strftime("%B %d, %Y")
    rows = ""
    for j in jobs:
        if j["score"] >= 3:
            badge = '<span style="background:#1a7f37;color:#fff;padding:2px 7px;border-radius:10px;font-size:11px;margin-left:6px;">Strong Match</span>'
        elif j["score"] >= 1:
            badge = '<span style="background:#9a6700;color:#fff;padding:2px 7px;border-radius:10px;font-size:11px;margin-left:6px;">Relevant</span>'
        else:
            badge = ""
        snip = f'<div style="font-size:13px;color:#374151;margin-top:8px;">{j["snippet"][:200]}</div>' if j.get("snippet") else ""
        rows += (f'<tr><td style="padding:16px;border-bottom:1px solid #e5e7eb;vertical-align:top;">'
                 f'<div style="font-size:16px;font-weight:600;"><a href="{j["url"]}" style="color:#2563eb;text-decoration:none;">{j["title"]}</a>{badge}</div>'
                 f'<div style="font-size:13px;color:#6b7280;margin-top:4px;">{j.get("company","")}'
                 f'{(" &bull; " + j["location"]) if j.get("location") else ""} &bull; {j.get("source","")}</div>{snip}</td></tr>')
    if not rows:
        rows = '<tr><td style="padding:32px;color:#6b7280;text-align:center;">No new roles today. Check back tomorrow!</td></tr>'
    return (f'<!DOCTYPE html><html><head><meta charset="UTF-8"></head>'
            f'<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif;">'
            f'<table width="100%" cellpadding="0" cellspacing="0" style="padding:30px 0;"><tr><td align="center">'
            f'<table width="640" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08);">'
            f'<tr><td style="background:linear-gradient(135deg,#1e3a5f,#2563eb);padding:30px 32px;">'
            f'<div style="color:#fff;font-size:22px;font-weight:700;">&#128188; Daily Job Digest</div>'
            f'<div style="color:#bfdbfe;font-size:13px;margin-top:4px;">{today} &bull; MD / VP / EVP / SVP &bull; AI &bull; Technology &bull; Managed Services</div>'
            f'</td></tr><tr><td style="background:#eff6ff;padding:12px 32px;border-bottom:1px solid #dbeafe;">'
            f'<span style="font-size:13px;color:#1e40af;">&#10003; <strong>{len(jobs)} new role{"s" if len(jobs)!=1 else ""}</strong> found today</span>'
            f'</td></tr><table width="100%" cellpadding="0" cellspacing="0">{rows}</table>'
            f'<tr><td style="padding:20px 32px;border-top:1px solid #e5e7eb;background:#f9fafb;">'
            f'<div style="font-size:11px;color:#9ca3af;">Digest for Windy Bartels &bull; MD/VP/EVP/SVP &bull; AI / IT Outsourcing / Managed Services / Cloud / Tech Consulting &bull; Open to Relocation</div>'
            f'</td></tr></table></td></tr></table></body></html>')


def send_email(html, job_count):
    subject = f"[Job Digest] {job_count} New Senior Role{'s' if job_count!=1 else ''} - {datetime.date.today()}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SMTP_USER
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(html, "html"))

    print(f"Connecting to smtp.office365.com:587 as {SMTP_USER} ...")
    with smtplib.SMTP("smtp.office365.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_USER, EMAIL_TO, msg.as_string())
    print(f"Email sent: {subject}")


def main():
    print(f"Daily Job Digest v5 - {datetime.datetime.utcnow().isoformat()}Z")
    seen = load_seen()
    all_jobs = []

    print("\nFetching Arbeitnow..."); all_jobs.extend(fetch_arbeitnow())
    print(f"  {len(all_jobs)} roles")
    print("\nFetching Remotive..."); before = len(all_jobs); all_jobs.extend(fetch_remotive())
    print(f"  +{len(all_jobs)-before}")
    print("\nFetching RemoteOK..."); before = len(all_jobs); all_jobs.extend(fetch_remoteok())
    print(f"  +{len(all_jobs)-before}")
    print("\nFetching The Muse..."); before = len(all_jobs); all_jobs.extend(fetch_the_muse())
    print(f"  +{len(all_jobs)-before}")

    new_jobs, new_ids = [], set()
    for job in all_jobs:
        jid = job_id(job["url"])
        if jid not in seen and jid not in new_ids:
            new_jobs.append(job); new_ids.add(jid)

    new_jobs.sort(key=lambda j: -j["score"])
    print(f"\nTotal: {len(all_jobs)} | New: {len(new_jobs)}")
    send_email(build_html(new_jobs), len(new_jobs))
    seen.update(new_ids)
    save_seen(seen)
    print("Done.")


if __name__ == "__main__":
    main()
