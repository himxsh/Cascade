# Cascade

An agent that turns a breaking schema PR into a coordinated migration — it reads DataHub lineage, rewrites the downstream code, opens the PRs, and writes the decision trail back to the graph.

## Challenge mapping

| Challenge | How Cascade maps |
|-----------|------------------|
| Agents That Do Real Work | Reasons over lineage, acts in GitHub, writes back to DataHub so the next agent inherits context |
| Metadata-Aware Code Generation | Rewrites downstream dbt/SQL from live schemas (primary path), schema-gated |

## Quick start

_Coming soon._

## Setup

1. Clone the repo
2. Copy `.env.example` → `.env` and fill in credentials
3. **DataHub (local):** see [`demo/datahub-quickstart.md`](demo/datahub-quickstart.md) to stand up a local DataHub instance
4. _(more coming soon)_

## Architecture

See [docs/](docs/) for spec, plan, and architecture diagrams.

## License

Apache 2.0 — see [LICENSE](LICENSE).
