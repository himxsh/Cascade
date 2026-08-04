# Cascade

An agent that turns a breaking schema PR into a coordinated migration — it reads DataHub lineage, rewrites the downstream code, opens the PRs, and writes the decision trail back to the graph.

## Challenge mapping

| Challenge | How Cascade maps |
|-----------|------------------|
| Agents That Do Real Work | Reasons over lineage, acts in GitHub, writes back to DataHub so the next agent inherits context |
| Metadata-Aware Code Generation | Rewrites downstream dbt/SQL from live schemas (primary path), schema-gated |

## One-command demo (fixture path)

```bash
pip install -e .
cascade demo --out artifacts/demo
```

Runs impact → generate → apply dry-run with no secrets. Inspect:

- `artifacts/demo/apply/pr_comment.md` — blast radius + agent rationale
- `artifacts/demo/apply/downstream_pr.diff` — rewritten mergeable SQL patch
- `artifacts/demo/apply/datahub_writeback.json` / `ml_writeback.json` — write-back payloads
- `examples/rewritten/headline_pr.diff` — static headline artifact (no run needed)

Full suite (includes golden-diff eval): `python -m unittest discover -s tests -v`

## Quick start (stepwise)

```bash
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

diff -u examples/rewritten/fct_orders.sql /tmp/cascade-out/fct_orders.sql
python -m unittest tests.test_golden_diff -v
```

### Fixture path: apply dry-run (Act + write-back)

```bash
cascade apply --report /tmp/cascade-out/impact_report.json --out /tmp/cascade-apply --mark-migrated
```

GitHub Action [`.github/workflows/cascade.yml`](.github/workflows/cascade.yml) runs the same fixture path and uploads artifacts. With `GITHUB_TOKEN` on a PR it posts the comment; DataHub live write-back stays off unless `CASCADE_WRITEBACK=1`.

### Data sources

| Flag | Behavior |
|------|----------|
| `--source fixture` (default) | Reads from the demo fixture |
| `--source live` | Reads from live DataHub GMS (`DATAHUB_GMS_URL`); fails if unhealthy |
| `--source auto` | Tries live GMS first; falls back to fixture with a stderr notice |

Live mode hydrates datasets, lineage, and owners from GMS GraphQL. ML features/models fall back to fixture. Set `DATAHUB_GMS_URL` and `DATAHUB_TOKEN` (optional) in the environment or `.env`.

## Setup

1. Clone the repo
2. Copy `.env.example` → `.env` and fill in credentials (optional for fixture path)
3. **DataHub (local):** see [`demo/datahub-quickstart.md`](demo/datahub-quickstart.md) to stand up a local DataHub instance
4. Env vars (see `.env.example`):

| Variable | Required for | Notes |
|----------|----------------|-------|
| `DATAHUB_GMS_URL` / `DATAHUB_TOKEN` | `--source live` / live write-back | GMS GraphQL + optional Bearer |
| `CASCADE_WRITEBACK=1` | Live DataHub/ML tags | Default is dry-run JSON artifacts |
| `GITHUB_TOKEN` / `GITHUB_REPOSITORY` / `CASCADE_PR_NUMBER` | Live PR comment | Action sets these on `pull_request` |
| `CASCADE_DOWNSTREAM_HEAD` / `CASCADE_DOWNSTREAM_BASE` | Live downstream PR | Head must already contain rewritten files |
| `LLM_API_KEY` | Optional LLM rewrite | Demo agent used when unset |

## Open-source Skill

Draft DataHub Skill [`breaking-change-remediation`](oss/datahub-skills/skills/breaking-change-remediation/SKILL.md) lives under [`oss/datahub-skills/`](oss/datahub-skills/) for now (in-repo only; do not open upstream until coordinated).

## Interactive UI (Phase 10)

Paste a schema diff → run Cascade (fixture path by default) → inspect blast radius, remediations, SQL diffs, and dry-run DataHub write-backs.

```bash
# terminal 1 — API (calls cascade/*; default source=fixture, works offline)
pip install -e ".[ui]"
uvicorn api.server:app --reload --port 8000

# terminal 2 — Vite app (proxies /api → :8000)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 → **Load demo diff** → **Run Cascade**.

Self-check (ImpactReport shape + fixture path):

```bash
python -m unittest tests.test_ui_run -v
```

### Deploy (Vercel)

One Vercel project: FastAPI (`api/server.py`) + static UI built into `public/`.

```bash
npx vercel --prod
```

Fixture path needs no secrets. Optional live DataHub: set `DATAHUB_GMS_URL` / `DATAHUB_TOKEN` in the Vercel project env.

## Architecture

See [docs/](docs/) for [spec](docs/spec.md), [plan](docs/plan.md), [progress](docs/progress.md), and architecture diagrams.

## License

Apache 2.0 — see [LICENSE](LICENSE).
