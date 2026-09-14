#!/usr/bin/env python3
"""Query every ATS-supported company in data/watchlist.json in one batch and print job
postings as JSON. Supports Greenhouse, Lever, Ashby, and Workday. Entries on other platforms
(e.g. "icims", "unknown") are skipped and reported separately so they can be checked manually
or via web search instead.

Usage:
    python3 scripts/check_boards.py [--watchlist data/watchlist.json]
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAULT_WATCHLIST = "data/watchlist.json"
TIMEOUT = 15
USER_AGENT = "job-hunt-system/1.0 (+https://github.com/)"


def _get_json(url, method="GET", body=None):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_greenhouse(entry):
    url = f"https://boards-api.greenhouse.io/v1/boards/{entry['slug']}/jobs?content=true"
    data = _get_json(url)
    jobs = []
    for job in data.get("jobs", []):
        jobs.append({
            "company": entry["company"],
            "platform": "greenhouse",
            "title": job.get("title"),
            "url": job.get("absolute_url"),
            "job_id": str(job.get("id")),
            "location": (job.get("location") or {}).get("name"),
        })
    return jobs


def fetch_lever(entry):
    url = f"https://api.lever.co/v0/postings/{entry['slug']}?mode=json"
    data = _get_json(url)
    jobs = []
    for job in data:
        jobs.append({
            "company": entry["company"],
            "platform": "lever",
            "title": job.get("text"),
            "url": job.get("hostedUrl"),
            "job_id": job.get("id"),
            "location": (job.get("categories") or {}).get("location"),
        })
    return jobs


def fetch_ashby(entry):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{entry['slug']}"
    data = _get_json(url)
    jobs = []
    for job in data.get("jobs", []):
        jobs.append({
            "company": entry["company"],
            "platform": "ashby",
            "title": job.get("title"),
            "url": job.get("jobUrl") or job.get("applyUrl"),
            "job_id": job.get("id"),
            "location": job.get("location"),
        })
    return jobs


def fetch_workday(entry):
    tenant = entry["tenant"]
    wd_host = entry["wd_host"]
    site = entry["site"]
    base = f"https://{tenant}.{wd_host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    jobs = []
    offset = 0
    limit = 20
    total = None
    while True:
        body = {"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": ""}
        data = _get_json(base, method="POST", body=body)
        postings = data.get("jobPostings", [])
        if not postings:
            break
        # Some Workday tenants only report the correct "total" on the first page and
        # return 0 on subsequent pages -- latch onto the first non-zero total we see
        # rather than re-reading it (and stopping early) every iteration.
        if total is None:
            total = data.get("total", 0)
        for job in postings:
            path = job.get("externalPath", "")
            jobs.append({
                "company": entry["company"],
                "platform": "workday",
                "title": job.get("title"),
                "url": f"https://{tenant}.{wd_host}.myworkdayjobs.com/{site}{path}",
                "job_id": job.get("bulletFields", [None])[0] or path,
                "location": job.get("locationsText"),
            })
        offset += limit
        if offset >= total or len(postings) < limit:
            break
    return jobs


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workday": fetch_workday,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--watchlist", default=DEFAULT_WATCHLIST)
    args = parser.parse_args()

    with open(args.watchlist) as f:
        watchlist = json.load(f)

    all_jobs = []
    skipped = []
    errors = []

    for entry in watchlist:
        platform = entry.get("platform")
        fetcher = FETCHERS.get(platform)
        if fetcher is None:
            skipped.append({"company": entry.get("company"), "platform": platform,
                             "reason": entry.get("notes", "unsupported platform")})
            continue
        try:
            all_jobs.extend(fetcher(entry))
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError) as exc:
            errors.append({"company": entry.get("company"), "platform": platform,
                            "error": str(exc)})

    result = {"jobs": all_jobs, "skipped": skipped, "errors": errors}
    print(json.dumps(result, indent=2))

    if errors:
        print(f"\n{len(errors)} board(s) failed to fetch.", file=sys.stderr)


if __name__ == "__main__":
    main()
