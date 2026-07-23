# Examples

## `diffs/`

- `raw_orders_rename_user_id.json` — JSON changes file (FIELD_RENAMED, heuristic)
- `raw_orders_rename_user_id.patch` — Unified diff with `-- cascade:` annotation, equivalent change

Both produce the same ImpactReport via `cascade impact --diff`.
