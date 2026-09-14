# job_search_claude

A Claude Code-driven job hunt system: finds, dedupes, scores, and tracks roles, and helps
tailor application materials. Based on
[How to Build a Job Hunt System with Claude Code](https://www.scottypeterson.net/blog/how-to-build-a-job-hunt-system-with-claude-code).

The philosophy: automate the funnel, not the judgment. Claude finds and scores roles;
Clementine decides what to apply to and reviews everything before it goes out.

## Structure

- `CLAUDE.md` — the decision engine: target profile, scoring rubric, workflow definitions,
  and guardrails. Read this first.
- `profile/` — source-of-truth career context.
  - `og-resume.md` — master resume. Never edited directly; copy and tailor per role.
  - `linkedin-profile.md` — LinkedIn context (draft, review before relying on it).
  - `projects.md` / `project_descriptions.Rmd` — full project history and abstracts.
  - `czimnicki_CV.pdf` — original PDF resume.
- `data/` — plain-text tracking.
  - `evaluated_jobs.csv` — every scored role.
  - `outreach_tracker.csv` — networking contacts and exact messages sent.
  - `job_tracker.csv` — application pipeline status.
  - `volunteer_tracker.csv` — skills-based volunteer opportunities.
  - `watchlist.json` — target companies with ATS platform + slug.
- `scripts/`
  - `check_boards.py` — queries every Greenhouse/Lever/Ashby/Workday company in
    `data/watchlist.json` in one batch and prints new postings as JSON.
  - `dedupe_jobs.py` — batch-dedupes a candidate list against `evaluated_jobs.csv` and itself.
- `daily_digest/` — one markdown digest per day of ranked roles.
- `resumes/` — per-company folders with saved job descriptions and tailored resumes.

## Usage

Start a session and ask Claude to run the daily workflow, paste a job to score, or search for
new roles — the steps for each are defined in `CLAUDE.md`. To add a company to the watchlist,
find its careers page, identify the ATS platform from the domain (see `CLAUDE.md`), and add an
entry to `data/watchlist.json`.

```
python3 scripts/check_boards.py                     # fetch all watchlisted boards
python3 scripts/dedupe_jobs.py candidates.json       # dedupe a batch of candidates
```
