#!/usr/bin/env python3
"""Batch-dedupe a list of candidate jobs against data/evaluated_jobs.csv and against each
other, using two keys: normalized (company, title) and a platform-specific job ID extracted
from the URL. Never check candidates one at a time -- always run the whole batch through this
in a single pass.

Usage:
    python3 scripts/dedupe_jobs.py candidates.json [--csv data/evaluated_jobs.csv]

candidates.json is a JSON array of objects with at least "company", "title"/"role", and "url"
(job_id is used if present, otherwise extracted from the URL). Prints a JSON object with
"new" (candidates that survived dedup) and "duplicates" (candidates dropped, with the reason).
"""

import argparse
import csv
import json
import re
import sys

DEFAULT_CSV = "data/evaluated_jobs.csv"

JOB_ID_PATTERNS = [
    re.compile(r"gh_jid=(\d+)"),
    re.compile(r"greenhouse\.io/.*?/jobs/(\d+)"),
    re.compile(r"jobs\.lever\.co/[^/]+/([0-9a-f-]{36})"),
    re.compile(r"jobs\.ashbyhq\.com/[^/]+/([0-9a-f-]{36})"),
    re.compile(r"/job/[^/]*_(R\d+)", re.IGNORECASE),
    re.compile(r"(R\d{5,})"),
]


def normalize_title(company, title):
    text = f"{company} {title}".lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\bthe\b", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_job_id(url):
    if not url:
        return None
    for pattern in JOB_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def load_existing_keys(csv_path):
    title_keys = set()
    id_keys = set()
    try:
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                company = row.get("Company", "")
                role = row.get("Role", "")
                url = row.get("URL", "")
                if company or role:
                    title_keys.add(normalize_title(company, role))
                job_id = extract_job_id(url)
                if job_id:
                    id_keys.add(job_id)
    except FileNotFoundError:
        pass
    return title_keys, id_keys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", help="Path to a JSON file with candidate jobs")
    parser.add_argument("--csv", default=DEFAULT_CSV)
    args = parser.parse_args()

    with open(args.candidates) as f:
        candidates = json.load(f)

    seen_titles, seen_ids = load_existing_keys(args.csv)

    new_jobs = []
    duplicates = []

    for candidate in candidates:
        company = candidate.get("company", "")
        title = candidate.get("title") or candidate.get("role", "")
        url = candidate.get("url", "")
        job_id = candidate.get("job_id") or extract_job_id(url)
        title_key = normalize_title(company, title)

        if job_id and job_id in seen_ids:
            duplicates.append({**candidate, "reason": f"duplicate job_id: {job_id}"})
            continue
        if title_key in seen_titles:
            duplicates.append({**candidate, "reason": f"duplicate title match: {title_key}"})
            continue

        new_jobs.append(candidate)
        seen_titles.add(title_key)
        if job_id:
            seen_ids.add(job_id)

    print(json.dumps({"new": new_jobs, "duplicates": duplicates}, indent=2))

    print(f"\n{len(new_jobs)} new, {len(duplicates)} duplicate(s) dropped.", file=sys.stderr)


if __name__ == "__main__":
    main()
