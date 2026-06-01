#!/usr/bin/env python3
"""
Daily Job Digest v7 - Console Output edition
Senior exec roles: MD, VP, EVP, SVP
Industries: AI, IT Outsourcing, Managed Services, Cloud, Technology Consulting

No email needed - results printed to console for direct viewing.
"""

import os, json, datetime, hashlib, time
from urllib.request import urlopen, Request
from urllib.parse import quote_plus
from urllib.error import URLError

SEEN_FILE = "seen_jobs.json"

TITLE_KEYWORDS = [
    "managing director", "vice president", " vp ", "vp,", "vp-",
    "evp", "svp", "executive vice president", "senior vice president",
]

RELEVANCE_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning",
    "managed services", "outsourcing", "cloud", "digital transformation",
    "technology consulting", "platform", "gsi", "governance",
    "portfolio", "enterprise", "saas", "it services", "cybersecurity",
    "automation", "analytics", "strategic",
]

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def make_id(url):
    return hashlib.md5(url.encode()).hexdigest()

def is_exec_title(title):
    t = title.lower()
    return any(k in t for k in TITLE_KEYWORDS)

def score_job(title, company, description=""):
    text = (title + " " + company + " " + description).lower()
    return sum(1 for k in RELEVANCE_KEYWORDS if k in text)

def fetch_arbeitnow():
    jobs = []
    try:
        url = "https://www.arbeitnow.com/api/job-board-api?page=1"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urlopen(req, timeout=10).read())
        for j in data.get("data", []):
            if is_exec_title(j.get("title", "")):
                jobs.append({
                    "title": j.get("title", ""),
                    "company": j.get("company_name", ""),
                    "location": j.get("location", "Remote"),
                    "url": j.get("url", ""),
                    "source": "Arbeitnow",
                    "description": j.get("description", "")[:300],
                })
    except Exception as e:
        print(f"  Arbeitnow error: {e}")
    return jobs

def fetch_remotive():
    jobs = []
    try:
        url = "https://remotive.com/api/remote-jobs?limit=100"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urlopen(req, timeout=10).read())
        for j in data.get("jobs", []):
            if is_exec_title(j.get("title", "")):
                jobs.append({
                    "title": j.get("title", ""),
                    "company": j.get("company_name", ""),
                    "location": j.get("candidate_required_location", "Remote"),
                    "url": j.get("url", ""),
                    "source": "Remotive",
                    "description": j.get("description", "")[:300],
                })
    except Exception as e:
        print(f"  Remotive error: {e}")
    return jobs

def fetch_remoteok():
    jobs = []
    try:
        url = "https://remoteok.com/api"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urlopen(req, timeout=10).read())
        for j in data:
            if not isinstance(j, dict) or "position" not in j:
                continue
            if is_exec_title(j.get("position", "")):
                jobs.append({
                    "title": j.get("position", ""),
                    "company": j.get("company", ""),
                    "location": j.get("location", "Remote"),
                    "url": j.get("url", ""),
                    "source": "RemoteOK",
                    "description": j.get("description", "")[:300],
                })
    except Exception as e:
        print(f"  RemoteOK error: {e}")
    return jobs

def fetch_themuse():
    jobs = []
    try:
        titles = ["Vice+President", "Managing+Director", "SVP", "EVP"]
        for t in titles:
            url = f"https://www.themuse.com/api/public/jobs?descending=true&page=1&per_page=20&category=Technology&level=Senior+Level&level=Director&query={t}"
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            try:
                data = json.loads(urlopen(req, timeout=10).read())
                for j in data.get("results", []):
                    title = j.get("name", "")
                    if is_exec_title(title):
                        locs = j.get("locations", [{}])
                        loc = locs[0].get("name", "Remote") if locs else "Remote"
                        jobs.append({
                            "title": title,
                            "company": j.get("company", {}).get("name", ""),
                            "location": loc,
                            "url": "https://www.themuse.com" + j.get("refs", {}).get("landing_page", ""),
                            "source": "The Muse",
                            "description": j.get("body", "")[:300],
                        })
            except:
                pass
            time.sleep(0.5)
    except Exception as e:
        print(f"  The Muse error: {e}")
    return jobs

def print_digest(jobs):
    if not jobs:
        print("\n  No new senior executive roles found today.")
        return

    print("\n" + "="*70)
    print(f"  DAILY JOB DIGEST - {datetime.datetime.utcnow().strftime('%B %d, %Y')}")
    print(f"  {len(jobs)} New Senior Executive Role(s) Found")
    print("="*70)

    # Sort by relevance score descending
    jobs_scored = [(j, score_job(j['title'], j['company'], j['description'])) for j in jobs]
    jobs_scored.sort(key=lambda x: x[1], reverse=True)

    for idx, (job, score) in enumerate(jobs_scored, 1):
        badge = "⭐ STRONG MATCH" if score >= 3 else ("✓ Relevant" if score >= 1 else "")
        print(f"\n{'─'*70}")
        print(f"  #{idx}  {job['title']}")
        print(f"  Company:  {job['company']}")
        print(f"  Location: {job['location']}")
        print(f"  Source:   {job['source']}")
        if badge:
            print(f"  Match:    {badge} (score: {score})")
        print(f"  Link:     {job['url']}")
        if job.get('description'):
            desc = job['description'].replace('<[^>]+>', '').strip()[:200]
            print(f"  Preview:  {desc}...")

    print(f"\n{'='*70}")
    print(f"  END OF DIGEST")
    print("="*70 + "\n")

def main():
    print(f"Daily Job Digest v7 - {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("Searching for MD / VP / EVP / SVP roles in AI, Tech, Managed Services...")
    print()

    seen = load_seen()
    all_jobs = []

    print("Fetching Arbeitnow...")
    jobs = fetch_arbeitnow()
    all_jobs.extend(jobs)
    print(f"  {len(jobs)} exec roles found")

    print("Fetching Remotive...")
    jobs = fetch_remotive()
    all_jobs.extend(jobs)
    print(f"  {len(jobs)} exec roles found")

    print("Fetching RemoteOK...")
    jobs = fetch_remoteok()
    all_jobs.extend(jobs)
    print(f"  {len(jobs)} exec roles found")

    print("Fetching The Muse...")
    jobs = fetch_themuse()
    all_jobs.extend(jobs)
    print(f"  {len(jobs)} exec roles found")

    print(f"\nTotal fetched: {len(all_jobs)}")

    # Deduplicate
    new_jobs = []
    new_seen = set(seen)
    for job in all_jobs:
        jid = make_id(job["url"])
        if jid not in seen:
            new_jobs.append(job)
            new_seen.add(jid)

    print(f"New (not seen before): {len(new_jobs)}")

    print_digest(new_jobs)
    save_seen(new_seen)

if __name__ == "__main__":
    main()
