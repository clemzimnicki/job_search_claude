# Job Hunt System — Decision Engine

This file is the judgment layer for the job hunt system. Read it at the start of every
session before evaluating, searching for, or applying to anything. The system's job is to
automate the funnel — finding, deduping, and scoring roles. Humans (Clementine) retain all
decision authority over what to apply to and what gets sent.

## Target Profile

**Candidate**: Clementine Zimnicki — PhD candidate in Psychology (UW-Madison, graduating Dec
2026), specializing in color perception, individual differences, and how information
visualization design affects decision-making under uncertainty. R&D Intern at Sandia National
Labs. Strong quantitative/experimental background (psychophysics, large-scale crowdsourced
studies, mixed-effects models), JavaScript/jsPsych/Python/R/MATLAB, IEEE VIS + Journal of
Vision publications, human factors and UX-adjacent applied research experience.

**Primary role types** (score these highly when the core function matches):
- UX Researcher / Research Scientist (quant or mixed-methods)
- Data Visualization researcher/engineer
- Human Factors / Human-Systems researcher or engineer
- Applied / Industry Research Scientist (general, not tied to one specialty above)

**Location**: Remote, hybrid, or on-site — open to relocating anywhere within the USA. Do not
penalize for location as long as the role is US-based. Roles based outside the USA are
excluded (see Hard Exclusions).

**Compensation target**: Base salary above $90k/year. Roles with a stated ceiling at or below
$90k are penalized heavily (see Scoring Rubric); do not exclude outright unless the range is
clearly and entirely below $90k with no ambiguity.

**Experience reality check**: Clementine has 6+ years of *academic/research* experience,
and 2+ years of experience at Sandia National Labs. She is an entry-level industry 
candidate with a PhD, not a senior IC. Postings that say "PhD" or "PhD + 0-3 years" 
(postdoc or industry) are a natural fit. Postings that require 5+ years of 
*industry* experience beyond the PhD should be treated as a minor gap; Sandia
National Labs is adjacent to industry and academia in that it is a government 
position. Don't disqualify a role if it is otherwise a very good fit. 

**Hard exclusions** (score 0, log with Notes: EXCLUDED, do not include in the daily digest):
- Academic/postdoc positions, faculty/lecturer roles, adjunct positions
- Roles based outside the USA

## Scoring Rubric

Score every role 0–100.

**Base score (role fit, 0–100)**: How well the role's core function matches one of the four
primary role types above. A role that is centrally a UX research, data viz, human factors, 
research operations, or applied research scientist role starts high (70–90 depending on 
specificity of match). A role that is adjacent (e.g., general data scientist, product 
analyst, quant researcher, project manager, client strategist) starts lower (40–60). 
A role with no meaningful overlap starts near 0 — do not force a score just to have 
something to log.

**Penalties applied** (subtract from base score, note each one applied):
- **Experience gap cap**: if the role requires more *industry* years than Clementine has (see
  Experience reality check above), deduct 1 point per year (e.g., 8+ years 
  industry experience = -8 points).
- **Missing required skill/platform**: −5 per required hard skill or platform she
  doesn't have experience with (e.g., a specific enterprise SaaS tool, a specific ML framework
  she hasn't used). Don't penalize for tools that are clearly learnable on the job or that
  overlap closely with something she knows (e.g., don't penalize "Figma" if she knows Adobe
  CC and design tools broadly).
- **Missing required degree**: -0 to -15 points depending on how far the degree 
  is from what Clementine's degrees are. E.g., sociology is -0; but Mechanical 
  Engineering is -15.
- **Compensation below target**: −10 if the stated range is entirely at or below $90k. −5 if
  the range straddles $90k (e.g., $80k–$100k).
- **AI-forward bonus**: +5 if the role explicitly involves LLM/AI-assisted workflows.
  Clementine has hands-on experience using Claude Code for experiment programming 
  and data analysis, but hasn't developed or engineered AI. 

**Thresholds**:
- 80+: strong fit, near-natural hire — surface prominently in the digest.
- 65–79: good fit, worth considering — include in digest, note the gaps.
- Below 65: weak fit — log to the CSV for the record, but don't feature in the digest.
- Hard-excluded categories: log with score 0, Notes: EXCLUDED, never feature.

## Job Board Integration

Discover a company's ATS platform from its careers page domain:
- `boards.greenhouse.io` or `job-boards.greenhouse.io` → Greenhouse
- `jobs.lever.co` → Lever
- `jobs.ashbyhq.com` → Ashby
- `*.myworkdayjobs.com` → Workday
- Anything else (ICIMS, custom career sites, etc.) → not API-supported; fall back to a
  targeted web search for that company instead of guessing an endpoint.

Public JSON endpoints (no auth required):
- Greenhouse: `https://boards-api.greenhouse.io/v1/boards/<slug>/jobs`
- Lever: `https://api.lever.co/v0/postings/<slug>?mode=json`
- Ashby: `https://api.ashbyhq.com/posting-api/job-board/<slug>`
- Workday: `POST https://<tenant>.<wd_host>.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs`
  (paginate 20 at a time via `offset`)

Use `scripts/check_boards.py` to query every company in `data/watchlist.json` in one batch
rather than fetching one at a time. When adding a new company to the watchlist, determine its
platform and slug from its careers page before adding — don't add a company with an unverified
platform without flagging it.

## Deduplication

Always dedupe before scoring or logging a new batch of candidate roles, using
`scripts/dedupe_jobs.py`. It matches on two keys against both `data/evaluated_jobs.csv` and
within the current candidate batch itself:

1. **Normalized title + company**: lowercased, punctuation stripped, leading "the" removed,
   whitespace collapsed.
2. **Platform job ID**: extracted per-platform (Greenhouse numeric id / `gh_jid`, Lever/Ashby
   UUID in the URL, Workday requisition ID like `R123456`).

Run dedup in batch mode against the whole CSV plus the whole candidate list at once — never
check candidates one at a time.

## Workflow Definitions

**When Clementine pastes a job description or URL**: check it against `data/evaluated_jobs.csv`
for duplicates first. If new, score it against the rubric above, append one row to
`data/evaluated_jobs.csv`, and stop — don't proceed to tailoring a resume or applying unless
asked.

**When asked to search for new roles**: only surface postings you can verify are live via a
company's own ATS (API or company careers page) — not aggregator listings (LinkedIn, Indeed,
etc.) that may be stale or reposted. Cap web search at 5 results per query, filter obviously
irrelevant snippets before fetching, then fetch each surviving candidate once.

**Daily/scheduled run**: 
1. Capture today's date.
2. Run `scripts/check_boards.py` against every company in `data/watchlist.json`.
3. Run a capped web search for additional roles matching the primary role types, filter
   snippets, batch-dedupe all candidates (from both sources) against the CSV and each other.
4. Score every surviving candidate against the rubric; append all new rows to
   `data/evaluated_jobs.csv` in one batched write, not one row at a time.
5. Generate a markdown digest in `daily_digest/YYYY-MM-DD.md` with roles grouped by tier
   (80+, 65–79), noting score and key gaps for each.
6. Commit the updated CSV and the new digest to git. Do not push unless Clementine has asked
   for pushes to happen automatically — confirm first the first time this runs.
- It's fine for a run to find nothing — "no new roles today" is a valid, complete result.
  Don't pad the digest or invent marginal matches to have something to show.

**When applying to a role**: save the job description into a per-company folder under
`resumes/<Company>/`, tailor a copy of `profile/og-resume.md` for that specific role (never
edit `profile/og-resume.md` itself), and export a PDF with the naming convention
`Zimnicki_<Company>_<Role>.pdf`. Do not apply anywhere, Clementine will do that. 
Only Clementine marks a row "Applied" in the CSV — do not set that field yourself 
even after generating materials.

**Outreach**: log every networking contact in `data/outreach_tracker.csv`, including the exact
message sent (not a paraphrase) and a follow-up date, so past conversations aren't
accidentally repeated or contradicted. Do not reach out to anyone, Clementine will
do that. 

## Guardrails

- `profile/og-resume.md` is the master resume. Never edit it in place — always copy it, tailor
  the copy for a specific role, and save the copy elsewhere (under `resumes/<Company>/`).
- Never fabricate experience, skills, publications, or metrics. If a role wants something
  Clementine doesn't have, that's a scoring penalty, not a reason to embellish the resume.
- Verify postings are live through the company's own ATS or careers page before including them
  — don't trust aggregator caches.
- Never mark a CSV row "Applied" or send an outreach message on Clementine's behalf without
  being asked to for that specific action.

## Writing Voice Rules

When drafting outreach messages, resume bullets, or digest summaries:
- Avoid em dashes.
- Avoid labeled-list patterns like "Trigger: X" / "Result: Y".
- Avoid rigid three-example formatting — vary sentence structure and list length instead.
- Keep outreach messages specific to the person and role, not templated boilerplate.

Do not send outreach messages, ever. Clementine will do that. 
