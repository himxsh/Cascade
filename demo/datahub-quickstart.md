# DataHub Quickstart

Stand up DataHub for Cascade. **GitHub Actions cannot reach `localhost`** — use
DataHub Cloud or a durable HTTPS GMS for the production loop; local Docker is for
laptop demos and offline seeding practice.

---

## Option A — DataHub Cloud / remote GMS (Actions + HTTPS)

1. Provision [DataHub Cloud](https://www.acryldata.io/) or a self-hosted GMS with HTTPS.
2. Create a token with **read** + **aspect ingest** (write) permissions.
3. Put secrets in the GitHub repo (Settings → Secrets) and in local `.env`:

```bash
DATAHUB_GMS_URL=https://<your-gms-host>
DATAHUB_TOKEN=<token>
```

4. Seed the demo graph (same script as local):

```bash
pip install -r demo/requirements.txt
export DATAHUB_GMS_URL=https://<your-gms-host>
export DATAHUB_TOKEN=<token>
python demo/seed_demo_graph.py --apply
```

5. Verify:

```bash
./demo/scripts/check_datahub.sh
# GraphQL smoke via Cascade:
python -c "from cascade.datahub_live import health_check, fetch_dataset; \
  assert health_check(); \
  print(fetch_dataset('urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)'))"
```

6. Optional Actions smoke: workflow [`.github/workflows/gms-smoke.yml`](../.github/workflows/gms-smoke.yml)
   (`workflow_dispatch` or nightly) when `DATAHUB_GMS_URL` / `DATAHUB_TOKEN` secrets exist.

---

## Option B — Local Docker (laptop only)

Stand up a local DataHub instance for Cascade development.

## Prerequisites

- **Docker Desktop** (or Docker Engine + Docker Compose v2)
- **~8 GB RAM** allocated to Docker
- **Python ≥ 3.8**

## Install DataHub CLI

```bash
pip install --upgrade acryl-datahub
```

Or via Homebrew (macOS / Linux):

```bash
brew install datahub-project/tap/datahub
```

## Start DataHub

```bash
datahub docker quickstart
```

On Apple Silicon (M1/M2/M3), pass `--arch m1`:

```bash
datahub docker quickstart --arch m1
```

First run pulls images (~5 min). Subsequent starts are faster.

## URLs

| Service      | URL                          |
|--------------|------------------------------|
| DataHub UI   | http://localhost:9002         |
| GMS API      | http://localhost:8080         |
| Default login| `datahub` / `datahub`        |

## Health check

```bash
datahub docker check
```

Or curl the GMS health endpoint directly:

```bash
curl -sf http://localhost:8080/health
```

Or use the bundled script (respects `DATAHUB_GMS_URL` env var):

```bash
./demo/scripts/check_datahub.sh
```

## Configure Cascade env

```bash
cp .env.example .env
```

Set in `.env`:

```
DATAHUB_GMS_URL=http://localhost:8080
DATAHUB_TOKEN=
```

`DATAHUB_TOKEN` can be empty for local quickstart (auth is disabled by default).

> **After quickstart: seed the demo graph**
>
> ```bash
> pip install -r demo/requirements.txt
> export DATAHUB_GMS_URL=http://localhost:8080
> python demo/seed_demo_graph.py --apply
> ```
>
> This emits 4 datasets (raw → stg → fct → features), 1 ML feature, 1 ML model,
> and the lineage edges between them. Run `python demo/check_demo_graph.py` first
> to validate the fixture without a live DataHub instance.

## Offline / fixture path

CI and `cascade demo` (default `--source fixture`) work with no GMS. Live path
(`--source live`, `CASCADE_WRITEBACK=1`) needs Option A or B above.

## Troubleshooting

- **Port conflicts**: Quickstart uses ports 3306, 9200, 9092, 8081, 2181, 9002, 8080.
  Stop other services on those ports or use `DATAHUB_MAPPED_PORT_*` env vars.
- **Apple Silicon**: Use `--arch m1` flag.
- **DataHub docs**: https://docs.datahub.com/docs/quickstart
