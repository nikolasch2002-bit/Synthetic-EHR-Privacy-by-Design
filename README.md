# Synthetic EHR + “Privacy-by-Design”

A realistic but entirely fake electronic health record, generated from a seed, and protected as if it were real. The plan is in [docs/project-spec.md](docs/project-spec.md); the clinical rules and the sources of their numbers are in [docs/clinical-rules.md](docs/clinical-rules.md).

## Generate the data

```
python -m uv sync
python -m uv run python -m generator                  # 25,000 patients into data/
python -m uv run python -m generator --population 200 --out data/small
```

It writes one CSV file per table, the identity table apart in `ehr_identity/`, and `manifest.sha256`. The same seed, config and locked dependencies (`uv.lock`) give byte-identical files; check them with `sha256sum -c manifest.sha256` in the output folder. `data/` is never committed: it is regenerated from the seed.
