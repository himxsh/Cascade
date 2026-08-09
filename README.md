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

GitHub Action [`.github/workflows/cascade.yml`](.github/workflows/cascade.yml) has two jobs:
- **fixture-ci** — hardcoded golden diff, no GMS secrets (always green offline path)
- **pr-impact** — on `pull_request`, `git diff` base…head for `*.sql` / `models/` / `schema.yml` → `cascade impact` (live GMS when `DATAHUB_GMS_URL` is set, else auto→fixture) → apply dry-run → PR comment

Map repo paths to DataHub URNs in [`.cascade/config.json`](.cascade/config.json) (or pass `--urn` / set `CASCADE_SOURCE_URN` / repo variable `CASCADE_SOURCE_URN`).

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
| `DATAHUB_GMS_URL` / `DATAHUB_TOKEN` | `--source live` / live write-back | HTTPS GMS for Actions; localhost only for laptop |
| `CASCADE_SOURCE_URN` | Optional URN when config mapping misses | Also repo Actions variable `CASCADE_SOURCE_URN` |
| `CASCADE_WRITEBACK=1` | Live DataHub/ML tags + docs | Default unset = dry-run JSON; never set on untrusted CI |
| `GITHUB_TOKEN` / `GITHUB_REPOSITORY` / `CASCADE_PR_NUMBER` | Live PR comment | Action sets these on `pull_request` |
| `CASCADE_DOWNSTREAM_HEAD` / `CASCADE_DOWNSTREAM_BASE` | Live downstream PR | Head must already contain rewritten files |
| `LLM_API_KEY` or `OPENAI_API_KEY` | LLM-primary strategy/rewrite | Deterministic demo agent when unset |
| `LLM_BASE_URL` | Optional OpenAI-compatible base | Default `https://api.openai.com/v1` |
| `LLM_MODEL` | Optional chat model id | Default `gpt-4o-mini` |

**LLM cost / latency:** When a key is set, Cascade calls the chat API once per downstream node (timeout 30s). Expect ~1–3s and a fraction of a cent per node on `gpt-4o-mini`; failures (timeout/parse/schema-gate) fall back to the deterministic rewrite with a stderr notice. Unset the key for offline/CI deterministic runs.

Repo secrets for live Actions: `DATAHUB_GMS_URL`, `DATAHUB_TOKEN`, `LLM_API_KEY`. Optional repo variable: `CASCADE_SOURCE_URN`. Smoke job: [`.github/workflows/gms-smoke.yml`](.github/workflows/gms-smoke.yml).

### URN mapping

[`.cascade/config.json`](.cascade/config.json) maps changed path prefixes → dataset URN (`default_urn` / `models_dir` optional). Longest matching prefix wins. Override with `--urn` or `CASCADE_SOURCE_URN`.

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
