#!/usr/bin/env python3
"""Query every ATS-supported company in data/watchlist.json in one batch and print job
postings as JSON. Supports Greenhouse, Lever, Ashby, Workday, Oracle Cloud HCM, SmartRecruiters,
Eightfold (keyword search only -- see fetch_eightfold), and amazon.jobs (keyword search only --
see fetch_amazon). Entries on other platforms
(e.g. "icims", "unknown") are skipped and reported separately so they can be checked manually
or via web search instead.

Usage:
    python3 scripts/check_boards.py [--watchlist data/watchlist.json]
"""

import argparse
import datetime
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_WATCHLIST = "data/watchlist.json"
TIMEOUT = 15
USER_AGENT = "job-hunt-system/1.0 (+https://github.com/)"
RETRY_DELAYS = (5, 15, 30, None)


def _get_json(url, method="GET", body=None):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    # Keyword-search boards (Eightfold) rate-limit bursts of queries with 429s -- back off and
    # retry a few times before giving up on the board.
    for delay in RETRY_DELAYS:
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or delay is None:
                raise
            time.sleep(delay)


def _date_from_ts(ts, ms=False):
    if not ts:
        return ""
    return datetime.date.fromtimestamp(ts / 1000 if ms else ts).isoformat()


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
            "posted": (job.get("first_published") or job.get("updated_at") or "")[:10],
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
            "posted": _date_from_ts(job.get("createdAt"), ms=True),
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
            "posted": (job.get("publishedAt") or "")[:10],
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
            if not job.get("title") or not path:
                # Occasionally a page returns a malformed/placeholder entry (seen when
                # postings open or close between paginated requests) -- skip it rather
                # than log an unusable row.
                continue
            jobs.append({
                "company": entry["company"],
                "platform": "workday",
                "title": job.get("title"),
                "url": f"https://{tenant}.{wd_host}.myworkdayjobs.com/{site}{path}",
                "job_id": job.get("bulletFields", [None])[0] or path,
                "location": job.get("locationsText"),
                "posted": job.get("postedOn"),
            })
        offset += limit
        if offset >= total or len(postings) < limit:
            break
    return jobs


def fetch_oracle(entry):
    """Oracle Cloud HCM candidate-experience sites (e.g. .../CandidateExperience/en/sites/<site>).
    Needs "host" (the fa-*.oraclecloud.com host) and "site" (the site number) in the entry.
    Results come newest first, so an optional entry["max_age_days"] stops paging early on large
    boards."""
    host = entry["host"]
    site = entry["site"]
    cutoff = None
    if entry.get("max_age_days"):
        cutoff = (datetime.date.today()
                  - datetime.timedelta(days=entry["max_age_days"])).isoformat()
    base = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    jobs = []
    offset = 0
    limit = 25
    while True:
        finder = f"findReqs;siteNumber={site},limit={limit},offset={offset},sortBy=POSTING_DATES_DESC"
        url = f"{base}?onlyData=true&expand=requisitionList&finder={urllib.parse.quote(finder, safe=';=,')}"
        data = _get_json(url)
        item = (data.get("items") or [{}])[0]
        reqs = item.get("requisitionList", [])
        for job in reqs:
            jobs.append({
                "company": entry["company"],
                "platform": "oracle",
                "title": job.get("Title"),
                "url": f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{job.get('Id')}",
                "job_id": str(job.get("Id")),
                "location": job.get("PrimaryLocation"),
                "country": job.get("PrimaryLocationCountry"),
                "posted": job.get("PostedDate"),
            })
        offset += limit
        if not reqs or offset >= item.get("TotalJobsCount", 0):
            break
        if cutoff and (reqs[-1].get("PostedDate") or "") < cutoff:
            break
    if cutoff:
        jobs = [job for job in jobs if (job["posted"] or "") >= cutoff]
    return jobs


def fetch_smartrecruiters(entry):
    base = f"https://api.smartrecruiters.com/v1/companies/{entry['slug']}/postings"
    jobs = []
    offset = 0
    limit = 100
    while True:
        data = _get_json(f"{base}?limit={limit}&offset={offset}")
        postings = data.get("content", [])
        for job in postings:
            loc = job.get("location") or {}
            jobs.append({
                "company": entry["company"],
                "platform": "smartrecruiters",
                "title": job.get("name"),
                "url": f"https://jobs.smartrecruiters.com/{entry['slug']}/{job.get('id')}",
                "job_id": str(job.get("id")),
                "location": loc.get("fullLocation") or loc.get("city"),
                "country": loc.get("country"),
                "posted": (job.get("releasedDate") or "")[:10],
            })
        offset += limit
        if not postings or offset >= data.get("totalFound", 0):
            break
    return jobs


def fetch_eightfold(entry):
    """Eightfold PCSX career sites (<tenant>.eightfold.ai/careers). Large employers post
    thousands of reqs there, so rather than pull the whole board this runs each keyword in
    entry["queries"] (newest first) and keeps postings from the last entry["max_age_days"]
    days (default 30)."""
    tenant = entry["tenant"]
    domain = entry["domain"]
    cutoff = datetime.datetime.now().timestamp() - entry.get("max_age_days", 30) * 86400
    jobs = {}
    for query in entry.get("queries", []):
        start = 0
        while True:
            params = urllib.parse.urlencode({"domain": domain, "query": query, "start": start,
                                             "sort_by": "timestamp"})
            data = _get_json(f"https://{tenant}.eightfold.ai/api/pcsx/search?{params}")["data"]
            positions = data.get("positions", [])
            for job in positions:
                if job.get("postedTs", 0) < cutoff:
                    continue
                jobs[job["id"]] = {
                    "company": entry["company"],
                    "platform": "eightfold",
                    "title": job.get("name"),
                    "url": f"https://{tenant}.eightfold.ai{job.get('positionUrl')}",
                    "job_id": str(job.get("displayJobId") or job["id"]),
                    "location": "; ".join(job.get("locations") or []),
                    "posted": _date_from_ts(job.get("postedTs")),
                    "pay_range": "; ".join(job.get("efcustomTextCustpayrange") or []),
                }
            start += len(positions)
            if (not positions or start >= data.get("count", 0)
                    or positions[-1].get("postedTs", 0) < cutoff):
                break
    return list(jobs.values())


def fetch_amazon(entry):
    """amazon.jobs search JSON. The board is enormous, so like fetch_eightfold this runs each
    keyword in entry["queries"] (US only, newest first) and keeps the last
    entry["max_age_days"] days (default 30). An optional entry["team"] (e.g. "team-lab126")
    keeps only postings from that team."""
    cutoff = datetime.date.today() - datetime.timedelta(days=entry.get("max_age_days", 30))
    jobs = {}
    for query in entry.get("queries", []):
        offset = 0
        while True:
            params = urllib.parse.urlencode({"base_query": query, "country": "USA",
                                             "sort": "recent", "result_limit": 100,
                                             "offset": offset})
            data = _get_json(f"https://www.amazon.jobs/en/search.json?{params}")
            postings = data.get("jobs", [])
            stop = False
            for job in postings:
                posted = datetime.datetime.strptime(" ".join(job["posted_date"].split()),
                                                    "%B %d, %Y").date()
                if posted < cutoff:
                    stop = True
                    continue
                if entry.get("team") and (job.get("team") or {}).get("label") != entry["team"]:
                    continue
                jobs[job["id_icims"]] = {
                    "company": entry["company"],
                    "platform": "amazon",
                    "title": job.get("title"),
                    "url": f"https://www.amazon.jobs{job.get('job_path')}",
                    "job_id": job["id_icims"],
                    "location": job.get("location"),
                    "posted": posted.isoformat(),
                }
            offset += len(postings)
            if stop or not postings or offset >= data.get("hits", 0):
                break
    return list(jobs.values())


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workday": fetch_workday,
    "oracle": fetch_oracle,
    "eightfold": fetch_eightfold,
    "smartrecruiters": fetch_smartrecruiters,
    "amazon": fetch_amazon,
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
