# Cascade

An agent that turns a breaking schema PR into a coordinated migration — it reads DataHub lineage, rewrites the downstream code, opens the PRs, and writes the decision trail back to the graph.

## Challenge mapping

| Challenge | How Cascade maps |
|-----------|------------------|
| Agents That Do Real Work | Reasons over lineage, acts in GitHub, writes back to DataHub so the next agent inherits context |
| Metadata-Aware Code Generation | Rewrites downstream dbt/SQL from live schemas (primary path), schema-gated |

## Quick start

```bash
pip install -e .
cascade impact \
  --urn 'urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)' \
  --diff examples/diffs/raw_orders_rename_user_id.json
```

Prints a JSON ImpactReport with blast radius, severity, and ML retrain suggestions.

`--diff` accepts a JSON changes file or a unified diff (`.patch` / `.sql.diff`). Diff content is auto-detected — JSON files start with `{` or `[`, everything else is parsed as a diff.

### Fixture path: impact → generate → golden

```bash
cascade impact \
  --urn 'urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)' \
  --diff examples/diffs/raw_orders_rename_user_id.json \
  --generate --models-dir examples/models --out /tmp/cascade-out

# rewritten SQL must match the golden / headline artifact
diff -u examples/rewritten/fct_orders.sql /tmp/cascade-out/fct_orders.sql

# full golden-diff eval (also runs in CI)
python -m unittest tests.test_golden_diff -v
```

Headline rewritten PR diff (no agent run needed): [`examples/rewritten/headline_pr.diff`](examples/rewritten/headline_pr.diff).

### Data sources

| Flag | Behavior |
|------|----------|
| `--source fixture` (default) | Reads from the demo fixture |
| `--source live` | Reads from live DataHub GMS (`DATAHUB_GMS_URL`); fails if unhealthy |
| `--source auto` | Tries live GMS first; falls back to fixture with a stderr notice |

Live mode hydrates datasets, lineage, and owners from GMS GraphQL. ML features/models fall back to fixture. Set `DATAHUB_GMS_URL` and `DATAHUB_TOKEN` (optional) in the environment or `.env`.

## Setup

1. Clone the repo
2. Copy `.env.example` → `.env` and fill in credentials
3. **DataHub (local):** see [`demo/datahub-quickstart.md`](demo/datahub-quickstart.md) to stand up a local DataHub instance
4. _(more coming soon)_

## Architecture

See [docs/](docs/) for spec, plan, and architecture diagrams.

## License

Apache 2.0 — see [LICENSE](LICENSE).
