# Examples

## `diffs/`

- `raw_orders_rename_user_id.json` — JSON changes file (FIELD_RENAMED, heuristic)
- `raw_orders_rename_user_id.patch` — Unified diff with `-- cascade:` annotation, equivalent change

Both produce the same ImpactReport via `cascade impact --diff`.

## `models/`

- `fct_orders.sql` — downstream dbt-style model that still projects `user_id` (pre-rewrite)

## `rewritten/` (headline artifact)

Static output of the generate path for the demo rename (`user_id` → `customer_id`):

- `fct_orders.sql` — rewritten mergeable SQL
- `headline_pr.diff` — the PR-shaped unified diff judges can read without running the agent

Regenerate (must match `tests/golden/raw_orders_rename/`):

```bash
cascade impact \
  --urn 'urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)' \
  --diff examples/diffs/raw_orders_rename_user_id.json \
  --generate --models-dir examples/models --out /tmp/cascade-out
cp /tmp/cascade-out/fct_orders.sql examples/rewritten/fct_orders.sql
```
