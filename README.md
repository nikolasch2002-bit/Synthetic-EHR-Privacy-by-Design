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
