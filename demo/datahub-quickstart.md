# DataHub Quickstart (local)

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

> **Seed script note:** The demo lineage graph (upstream + 3-4 downstream entities)
> is a separate checkpoint — not implemented here. See `docs/spec.md §9` for the graph
> shape and `docs/progress.md` for current status.

## Offline / fixture path

Per spec decision #7, the demo video will be recorded against the **offline fixture
path** (pre-seeded data, no live DataHub needed). The live quickstart is for local
development and testing.

## Troubleshooting

- **Port conflicts**: Quickstart uses ports 3306, 9200, 9092, 8081, 2181, 9002, 8080.
  Stop other services on those ports or use `DATAHUB_MAPPED_PORT_*` env vars.
- **Apple Silicon**: Use `--arch m1` flag.
- **DataHub docs**: https://docs.datahub.com/docs/quickstart
