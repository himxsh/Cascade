# Demo

Seed data, fixture dumps, and quickstart assets for the Cascade demo scenario live here.

See [docs/spec.md §9](../docs/spec.md) for the dataset graph.

- [DataHub quickstart](datahub-quickstart.md) — stand up a local DataHub instance
- [`scripts/check_datahub.sh`](scripts/check_datahub.sh) — health check (respects `DATAHUB_GMS_URL`)

## Fixture

[`fixtures/demo_graph.json`](fixtures/demo_graph.json) — static description of the demo
lineage graph (datasets, fields, lineage edges, ML feature→model, owners).

## Validate the fixture (no DataHub needed)

```bash
python check_demo_graph.py
```

## Seed into DataHub

Requires the `acryl-datahub` SDK:

```bash
pip install -r requirements.txt
export DATAHUB_GMS_URL=http://localhost:8080   # or set in .env
python seed_demo_graph.py                      # dry-run (print what would be emitted)
python seed_demo_graph.py --apply              # emit to live GMS
```
