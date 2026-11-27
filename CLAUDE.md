# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A portfolio project: a realistic but entirely fake electronic health record (patients, visits, diagnoses, medications, labs), generated in Python with `Faker` and explicit clinical rules, with a normalized source schema, analytical marts, a small app for cohorts, visit timelines and drug–lab interactions, and a governance pack (data dictionary, pseudonymization, access control, DPIA-style checklist). It is for recruiters and interviewers in health data roles, and it should prove clinical understanding, schema design, an application built end to end, a deliberate software development life cycle, and privacy-by-design with a test behind every control.

**[docs/project-spec.md](docs/project-spec.md) is the source of truth.** It defines the scope (what is in and out), the design, the questions the project answers, and each deliverable with the test that proves it. Read the relevant section before building any part.

Current state: milestones weeks 1–5 done and merged into `main` on 2026-11-27 (pull requests #14–#18, one per week). Built: the generator (40,000 patients), the `ehr` schema in local Postgres with the loader, pseudonymized dbt marts, the drug–lab events and the RAAS-start cohort with the rule score, and questions 1, 3, 5 (rule part), 6 and 7 in `analytics/RESULTS.md`. Every clinical and design decision in weeks 1–5 was drafted by the assistant; they are listed in each week's PR and in `docs/clinical-rules.md`. ADRs 0001–0004 accepted. Week 6 merged (#20): the prediction model, `ml/RESULTS.md`, and `governance/model-card.md` as a draft whose EU AI Act section I verify against EUR-Lex and rewrite in week 9. Week 7 (roles, row-level security, audit, `marts_public` with suppression, the publish script tested against a local stand-in): see its PR. Next: week 8, the app, and the hosted database (I create the provider account).

## Lessons from earlier projects

Read [docs/lessons-learned.md](docs/lessons-learned.md) before planning: section 3 (pitfalls and the rule each one left) and section 4 (the setup checklist). It comes from the project starter.

## How we work

- The spec (`docs/project-spec.md`) is the source of truth. Implement the design; do not invent scope. If the spec is wrong, say so, and record the change with its reason.
- One step at a time. After each step, explain in plain words what changed and why, then ask before committing. Never commit, push or merge without my word.
- Clinical, domain and design decisions are mine. Give options and a recommendation, then wait.
- I must be able to explain every line. Keep changes small; comment non-obvious SQL.
- Small commits whose messages say why. Changes reach main through a pull request, merged with a merge commit after CI passes. Auto-merge stays off.
- Every claim needs a proof that runs. After writing a test, show that it can fail.
- Report numbers from command output. Say plainly what is not done or not verified.
- Never read or print secrets: check them by presence or length only.
- Read a file before overwriting it.
- Documents I must own (decision records, legal notes) are drafts until I rewrite them.

## Rules for this project

- **Data:** every row is generated from a seed; no real person's data is ever used or read. The generated dataset is not committed (it is regenerated from the seed); a small test sample (≤ 50 patients) may be. Identifiers live only in the identity schema; the public app reads only aggregates after small-cell suppression. The hosted database holds only `marts_public`, copied by the publish script; nothing else ever leaves the local and CI databases. Generated data may be shown in an AI chat. The full table is in the spec's "Data" section.
- **Identifiers:** every invented identifier uses a format no real person can have (prefix `SYN-`). Never use Faker's national ID generators.
- **Prediction model:** one logistic regression for hyperkalaemia after a RAAS-inhibitor start, against a rule baseline (spec, "Prediction model"). Call it a statistical model, and never claim it works on real patients: it learns the generator, not medicine. Features must come from before the index date.
- **Out of scope:** any other model, deep learning; synthetic data derived from real data; free-text notes, imaging, vital signs, microbiology, billing; FHIR, HL7 v2, OMOP; real authentication; clinical validity.
- **Secrets:** `.env` and `.streamlit/secrets.toml` (the pseudonymization key and database connection strings will live there). They are gitignored and denied to the assistant in `.claude/settings.json`.

## Commands

- Install: `python -m uv sync`
- Lint: `python -m uv run ruff check .` and `python -m uv run ruff format --check .`
- Test: `python -m uv run pytest` (database tests need the local Postgres: `docker compose up -d --wait`)
- Generate, load, build, answer: `python -m uv run python -m generator`, `... -m loader`, `... -m transform`, `... -m analytics`
- Pre-commit, once per clone: `python -m uv run pre-commit install`

On this Windows machine `uv` runs as `python -m uv`, and `gh` is at `C:\Program Files\GitHub CLI\gh.exe`. The local Python is 3.15; the project pins 3.12 (`.python-version`), which uv installs.

## Architecture and environment

- **CI:** GitHub Actions (`.github/workflows/ci.yml`) on every push: lint, secret scan of every pushed commit, tests. Actions pinned to commit hashes; Dependabot proposes updates.
- **Database:** PostgreSQL 16, locally in Docker; in CI a fresh Postgres service container per run, built from the seed (no hosted database, no database secrets in CI). Local: `docker-compose.yml`, container `synthetic-ehr-db` on 127.0.0.1:5433 (5433 so it never clashes with another local Postgres). Database tests use their own `<name>_test` database.
- **Transforms:** dbt-core with dbt-postgres ([ADR 0001](docs/adr/0001-postgres-and-dbt.md)). Every policy, grant and trigger on a dbt-built table is created by dbt in a `post_hook`; roles and table-independent functions are created by a script before dbt runs.
- **App:** Streamlit ([ADR 0003](docs/adr/0003-streamlit-hosted-local.md)), in two modes. **Hosted** (Streamlit Community Cloud, public): its secrets hold only the `public_app` login; aggregates only, no role switcher, no patient timeline. **Local:** the role switcher, the timeline and the identifiable screens. Never give the hosted app any other login. Not built yet.
- **Hosting for the database:** a free hosted Postgres for the hosted app, holding only `marts_public` ([ADR 0004](docs/adr/0004-population-and-hosted-data.md)); provider chosen when it is set up (week 7).
- **Generator defaults (config):** 40,000 patients (raised from 25,000 in week 2 for enough model events), Faker locale `nl_NL`, history 2016-01-01 to 2025-12-31, reference date 2025-12-31; RAAS-inhibitor starts counted from 2017-01-01.
- **Secrets:** `.env` holds `POSTGRES_PASSWORD`, `DATABASE_URL` and `PSEUDONYM_KEY`, all created by a script and never printed. CI uses a throwaway container password and a fresh random pseudonym key per run. `.env.example` (denied to the assistant) still needs the three names added by me.
