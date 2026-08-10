# Cascade SQL rewrite skill

Remediate one downstream SQL model after upstream schema changes.
Trust **only** the provided `Changes` list and the given `Model SQL`. Invent nothing.

## Output (JSON only)
- `strategy`: `rewrite` | `adapter_view` | `deprecate`
- `rationale`: one line
- `sql`: full file contents if `rewrite`, else `null`

## Closed world
1. Every identifier edit must be justified by an entry in `Changes`.
2. If a column / type / nullability is not named in `Changes`, leave every occurrence unchanged — including names that look similar, share a prefix/suffix, or sit in the same SELECT list.
3. Never invent columns, tables, CTEs, filters, casts, coalesces, or default literals “to be helpful”.
4. Never apply a transform pattern (insert/delete/replace substrings, pluralize, add `_usd`, strip units, etc.) to identifiers that were not explicitly listed.
5. If the safe edit is unclear, choose `adapter_view` or `deprecate` with `sql: null` — do not guess.

## FIELD_RENAMED (`from` → `to`)
6. Upstream now exposes **`to`**. Downstream reads must use **`to`** (in SELECT, JOIN/ON, WHERE, GROUP BY, ORDER BY, and expressions).
7. Compatibility alias that preserves the old **output** name: ``to AS from``. Never ``from AS to`` (that assumes the old physical column still exists).
8. Do not alias some other column to `to` unless that expression already referenced `from` or `to` for **this** rename.
9. Update join keys the same way as select lists: if the predicate used `from`, switch that side to `to`.
10. One listed rename must not cascade into unrelated identifiers (substring / lookalike edits are forbidden).

## FIELD_REMOVED
11. Remove references to the removed field, or choose `adapter_view` / `deprecate`.
12. Do not substitute a different column unless `Changes` names an explicit replacement (`to` / mapping). No silent swaps.

## FIELD_TYPE_CHANGED
13. Keep the column name. Adjust only casts/comparisons required by the new type when the change states it.
14. Do not rename the column or change grain/aggregation unless `Changes` says so.

## Edit discipline
15. Return the **entire** model SQL, not a patch. Preserve formatting, comments, and unrelated clauses.
16. Prefer the smallest diff that makes the model valid against the new upstream schema.
17. Do not “improve” naming, performance, style, or business logic.
18. Table/schema/database qualifiers in FROM/JOIN are not column renames — leave them unless `Changes` targets them.

## Strategy choice
- `rewrite` — every needed fix is a direct, evidence-backed SQL edit.
- `adapter_view` — a shim/alias layer is safer than editing this model (missing model file, ambiguous impact, partial knowledge).
- `deprecate` — model cannot be safely repaired from `Changes` alone.
