# Synthetic EHR + “Privacy-by-Design”

A realistic but entirely fake electronic health record, generated from a seed, and protected as if it were real. The plan is in [docs/project-spec.md](docs/project-spec.md); the clinical rules and the sources of their numbers are in [docs/clinical-rules.md](docs/clinical-rules.md).

## Generate the data

```
python -m uv sync
python -m uv run python -m generator                  # 40,000 patients into data/ (about 2.5 minutes)
python -m uv run python -m generator --population 200 --out data/small
```

It writes one CSV file per table, the identity table apart in `ehr_identity/`, and `manifest.sha256`. The same seed, config and locked dependencies (`uv.lock`) give byte-identical files; check them with `sha256sum -c manifest.sha256` in the output folder. `data/` is never committed: it is regenerated from the seed.

## Run the database

PostgreSQL 16 runs locally in Docker, on `127.0.0.1:5433` only. It needs two settings in `.env` (gitignored, never committed):

```
POSTGRES_PASSWORD=<a long random password>
DATABASE_URL=postgresql://ehr_admin:<the same password>@127.0.0.1:5433/synthetic_ehr
```

```
docker compose up -d --wait                 # start Postgres
python -m uv run python -m loader           # rebuild the ehr schemas and load data/
python -m uv run pytest                     # the database tests use their own <name>_test database
```

The loader checks the manifest first and loads in one transaction, so a failed load leaves the database as it was. The schema is in [db/ehr_schema.sql](db/ehr_schema.sql); every column is described in [governance/data-dictionary.md](governance/data-dictionary.md). In CI, each run gets a fresh Postgres container, built from data generated from the seed.

## Build the marts and answer the questions

```
python -m uv run python -m transform        # pseudonyms, then dbt build (models and dbt tests)
python -m uv run python -m analytics        # writes analytics/RESULTS.md
```

`transform` needs `PSEUDONYM_KEY` in `.env`: 64 hex characters, e.g. from `python -c "import secrets; print(secrets.token_hex(32))"`. It computes each patient's pseudonym (HMAC-SHA-256) in Python and writes only the link to `ehr_link`; the key never reaches the database or dbt's files. The marts are in [dbt/models/marts](dbt/models/marts); the questions are in [analytics/](analytics/), with their answers in [analytics/RESULTS.md](analytics/RESULTS.md), small counts suppressed.

## The prediction model

```
python -m uv run python -m ml               # writes ml/RESULTS.md, ml/results.json, ml/calibration.png
```

One logistic regression for hyperkalaemia after a RAAS-inhibitor start, against a hand-written rule score: split by patient, fitted on the training set only, evaluated on the test set, and checked against the effects the generator planted. It is a statistical model of this project's own fake data: **it learns the generator, not medicine**, and says nothing about real patients. Results: [ml/RESULTS.md](ml/RESULTS.md). Model card: [governance/model-card.md](governance/model-card.md).
