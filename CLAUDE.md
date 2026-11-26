# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A portfolio project: a realistic but entirely fake electronic health record (patients, visits, diagnoses, medications, labs), generated in Python with `Faker` and explicit clinical rules, with a normalized source schema, analytical marts, a small app for cohorts, visit timelines and drug–lab interactions, and a governance pack (data dictionary, pseudonymization, access control, DPIA-style checklist). It is for recruiters and interviewers in health data roles, and it should prove clinical understanding, schema design, an application built end to end, a deliberate software development life cycle, and privacy-by-design with a test behind every control.

**[docs/project-spec.md](docs/project-spec.md) is the source of truth.** It defines the scope (what is in and out), the design, the questions the project answers, and each deliverable with the test that proves it. Read the relevant section before building any part.

Current state: milestone week 0. Starter setup done: CI green (lint, secret scan, tests), `main` protected, secret scan proven with a fake key. Spec drafted; D4 decided (a prediction model, 2026-11-26); D1, D2, D3 and D5 open.

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

- **Data:** every row is generated from a seed; no real person's data is ever used or read. The generated dataset is not committed (it is regenerated from the seed); a small test sample (≤ 50 patients) may be. Identifiers live only in the identity schema; the public app reads only aggregates after small-cell suppression. Generated data may be shown in an AI chat. The full table is in the spec's "Data" section.
- **Identifiers:** every invented identifier uses a format no real person can have (prefix `SYN-`). Never use Faker's national ID generators.
- **Prediction model:** one logistic regression for hyperkalaemia after a RAAS-inhibitor start, against a rule baseline (spec, "Prediction model"). Call it a statistical model, and never claim it works on real patients: it learns the generator, not medicine. Features must come from before the index date.
- **Out of scope:** any other model, deep learning; synthetic data derived from real data; free-text notes, imaging, vital signs, microbiology, billing; FHIR, HL7 v2, OMOP; real authentication; clinical validity.
- **Secrets:** `.env` and `.streamlit/secrets.toml` (the pseudonymization key and database connection strings will live there). They are gitignored and denied to the assistant in `.claude/settings.json`.

## Commands

- Install: `python -m uv sync`
- Lint: `python -m uv run ruff check .` and `python -m uv run ruff format --check .`
- Test: `python -m uv run pytest`
- Pre-commit, once per clone: `python -m uv run pre-commit install`

On this Windows machine `uv` runs as `python -m uv`, and `gh` is at `C:\Program Files\GitHub CLI\gh.exe`. The local Python is 3.15; the project pins 3.12 (`.python-version`), which uv installs.

## Architecture and environment

- **CI:** GitHub Actions (`.github/workflows/ci.yml`) on every push: lint, secret scan of every pushed commit, tests. Actions pinned to commit hashes; Dependabot proposes updates.
- **Database, transforms, app, hosting:** not chosen yet (spec decisions D1 and D3).
- **Secrets:** none yet.
