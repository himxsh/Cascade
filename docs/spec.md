# Cascade — Product Spec

**Version:** 0.1  
**Status:** Draft  


---

## 1. Problem

A schema change (rename, drop, type change) looks local in a PR, but its blast radius is not. It ships *uncoordinated*: the author cannot see which downstream dbt models, pipelines, dashboards, and ML features depend on the column, so downstream owners discover the break after merge. Catalogs can *show* the blast radius; they do not **rewrite the downstream code**, open the coordinated PRs, or leave a durable decision trail for the next human or agent.

> Framing note: we do **not** claim to catch *silent* data-plane failures (frozen loads, drift the catalog can't see) — that is a different, already-occupied problem. Cascade's job is turning a **declared, uncoordinated schema change into a coordinated migration** before it lands.

---



## 2. Solution

**Cascade** is a GitHub-native **agent** that reads DataHub for real context, *reasons* about how to remediate each downstream dependency, generates the code, opens the PRs, and writes the outcome back to DataHub.

1. Detects schema-affecting PRs
2. Reads real schemas, lineage, and ownership from **DataHub** (MCP / Agent Context Kit)
3. **Reasons** per downstream dependency: selects a remediation strategy from context (see §2.1) and **rewrites the downstream model SQL** — grounded in live schema, validated so it never references a column DataHub doesn't have
4. Opens coordinated downstream PRs / reviews
5. **Writes results back** into DataHub (docs, tags, descriptions)

One-liner for Devpost: *An agent that turns a breaking schema PR into a coordinated migration — it reads DataHub lineage, rewrites the downstream code, opens the PRs, and writes the decision trail back to the graph.*

### 2.1 Where the "agent" is (not a script)

This is **The Agent Hackathon**, so the LLM reasoning must be real and visible, not a deterministic template pipeline. Deterministic parts (diff parsing, lineage traversal, schema validation, GitHub calls) are **tools**. The LLM owns the judgment:

- **Strategy selection** per downstream node, chosen from context (change type + lineage depth + owner + severity + whether the node feeds an ML feature):
  - `rewrite` — edit the downstream model SQL to use the new column (primary path; this is the "code a team would merge")
  - `adapter_view` — compatibility shim aliasing old→new (backstop when a safe rewrite isn't derivable, or to buy a migration window)
  - `deprecate` — fail-fast + owner note when neither is safe (e.g. hard column drop with no replacement)
- **SQL rewriting** of the affected model, emitted only after passing the schema-validation gate (NF2).
- **Justification**: every remediation carries a one-line rationale that appears in the PR comment and the DataHub write-back — this is what the demo shows on camera to prove reasoning happened.

**Primary codegen story =** `rewrite`**.** `adapter_view` is the fallback, not the headline, so the "metadata-aware code generation" claim holds up under judge scrutiny.

---



## 3. Users & use cases


| Actor              | Job                                                                      |
| ------------------ | ------------------------------------------------------------------------ |
| Data engineer      | Open a breaking PR; get automatic impact + fix PRs                       |
| Downstream owner   | Review a Cascade-generated patch instead of discovering breakage in prod |
| Platform / ML team | Trust that model/feature deps are in the blast-radius path               |
| Judge / reviewer   | Clone repo, run demo, inspect `examples/` without a live warehouse       |




### Primary use case (demo)

Upstream table `analytics.raw_orders` renames `user_id` → `customer_id`. Three dbt models and one feature table depend on it. Cascade comments on the PR, opens a remediation PR with adapter/shim SQL, tags the dataset in DataHub, and attaches a change plan document.

---



## 4. Challenge mapping


| Hackathon challenge                 | How Cascade maps                                                                                                                                               |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Agents That Do Real Work            | Reasons over lineage, acts in GitHub, writes back to DataHub so the next agent inherits context                                                                |
| Metadata-Aware Code Generation      | Rewrites downstream dbt/SQL from live schemas (primary path), schema-gated                                                                                     |
| Production ML Agents (in MVP, thin) | Seed one `mlFeature`→`mlModel` edge; when a change hits a feature column, tag the model `cascade:retrain-suggested` and write an incident doc on the model URN |


Touching all three categories with **one run** is a deliberate originality multiplier — but depth of the code-gen + write-back loop is the priority; the ML node stays thin in MVP (one edge, one tag, one doc).

---



## 5. Functional requirements



### 5.1 Must have (MVP)


| ID  | Requirement                                                                                                                                                                                                                           |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F1  | Parse PR diffs for SQL/dbt schema changes: field removed, renamed, type changed. Rename detection runs a **heuristic first**; an optional `# cascade: rename a -> b` annotation *confirms/overrides*, it is not required to trigger   |
| F2  | Resolve affected dataset URN(s) via DataHub search / config mapping                                                                                                                                                                   |
| F3  | Fetch schema + downstream lineage + owners via MCP tools                                                                                                                                                                              |
| F4  | **Agentic step:** for each downstream node, the LLM selects a strategy (`rewrite` / `adapter_view` / `deprecate`, see §2.1) with a one-line rationale, using lineage + owner + severity context                                       |
| F5  | **Primary codegen:** `rewrite` the affected downstream model SQL to use the new schema. Every emitted file passes the schema-validation gate — it may only reference columns present in DataHub (NF2). `adapter_view` is the fallback |
| F6  | Produce a structured **ImpactReport** (JSON): change, nodes, owners, severity, chosen strategy + rationale per node                                                                                                                   |
| F7  | Post ImpactReport summary (with per-node rationale) as a GitHub PR comment                                                                                                                                                            |
| F8  | Open or update at least one downstream PR with the rewritten files                                                                                                                                                                    |
| F9  | Write-back: `save_document`, `add_tags` (`cascade:breaking-pending`), `update_description`                                                                                                                                            |
| F10 | **ML (thin):** if a changed column feeds a seeded `mlFeature`, tag the linked `mlModel` `cascade:retrain-suggested` and write an incident doc on the model URN                                                                        |
| F11 | **Eval / self-check in MVP:** ≥1 golden schema-diff → snapshot of expected ImpactReport + rewritten SQL, run in CI (satisfies "does it actually work end-to-end" and the one-runnable-check rule)                                     |
| F12 | Ship static samples under `examples/`, including **the one headline artifact**: a real, readable rewritten downstream PR diff a data team would merge                                                                                 |
| F13 | Public repo with Apache 2.0 license; runnable README                                                                                                                                                                                  |




### 5.2 Should have


| ID  | Requirement                                                                                                            |
| --- | ---------------------------------------------------------------------------------------------------------------------- |
| S1  | Clear pending tag → `cascade:migrated` when remediation merges                                                         |
| S2  | Request review from DataHub owners (GitHub usernames if mapped)                                                        |
| S3  | CLI for local dry-run without GitHub (`cascade impact`, `cascade generate`)                                            |
| S4  | Fixture/offline mode when MCP unavailable (demo resilience — record the video against this path)                       |
| S5  | DataHub **Skill** PR (`breaking-change-remediation`) opened **before** the deadline, not after (named bonus criterion) |




### 5.3 Nice to have (cut first)

Mapped to the **full plan** in [plan.md](./plan.md) (Phases 5–10) if the demo MVP ships early.


| ID  | Requirement                                                          | Full-plan phase |
| --- | -------------------------------------------------------------------- | --------------- |
| N1  | Multi-repo PR train                                                  | 6               |
| N2  | Slack notify owners                                                  | 6               |
| N3  | Airflow/Prefect DAG / tests generation                               | 6               |
| N4  | Upstream contribution: DataHub Skill for breaking-change remediation | 9               |
| N5  | Dashboard / LookML consumer patches                                  | 6 / 10          |
| N6  | Column-level severity + idempotent Action                            | 5               |
| N7  | ML model/feature retrain tagging                                     | 7               |
| N8  | Runtime schema-drift listener                                        | 8               |
| N9  | Policy status check + minimal paste-diff UI                          | 10              |


---



## 6. Non-functional requirements


| ID  | Requirement                                                                       |
| --- | --------------------------------------------------------------------------------- |
| NF1 | Demo path completes in ≤5 minutes on a laptop with Docker                         |
| NF2 | Agent must not invent column names (schema gate)                                  |
| NF3 | Secrets via env only (`DATAHUB_GMS_URL`, token, `GITHUB_TOKEN`) — never committed |
| NF4 | Deterministic ImpactReport for the seeded graph (self-check)                      |
| NF5 | Video ≤3 minutes showing live functionality                                       |


---



## 7. DataHub integration contract



### Read (MCP)

- `search` / `get_entities` — resolve assets
- `list_schema_fields` — ground generation
- `get_lineage` — blast radius (downstream)
- Entity aspects: owners, tags, glossary (for severity + reviewers)



### Write (MCP)

- `save_document` — change plan / incident narrative
- `add_tags` / `remove_tags` — lifecycle tags
- `update_description` — dated note on source dataset



### Explicit non-use

Do not rebuild Analytics Agent text-to-SQL as the product surface.

---



## 8. Interfaces



### CLI

```text
cascade impact  --diff <path|stdin> [--urn <datasetUrn>]
cascade generate --report <impact.json> --out <dir>
cascade apply   --report <impact.json>   # GitHub + DataHub write-back (CI)
cascade demo    # runs seeded scenario end-to-end
```



### GitHub Action inputs

- Trigger: `pull_request` on paths `**/*.sql`, `**/models/**`, `**/schema.yml`
- Secrets: DataHub + GitHub tokens
- Outputs: PR comment + optional downstream PR URL



### ImpactReport (sketch)

```json
{
  "source_urn": "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)",
  "changes": [
    {"type": "FIELD_RENAMED", "from": "user_id", "to": "customer_id", "detected_by": "heuristic"}
  ],
  "downstream": [
    {"urn": "...", "type": "dataset", "owners": ["urn:li:corpuser:alice"]}
  ],
  "ml_impact": [
    {"model_urn": "urn:li:mlModel:(...)", "via_feature": "user_id", "action": "retrain-suggested"}
  ],
  "severity": "high",
  "remediations": [
    {
      "path": "models/marts/fct_orders.sql",
      "strategy": "rewrite",
      "rationale": "user_id is projected in the final select and joined to dim_users; rewrite both references to customer_id"
    }
  ]
}
```

Note: `strategy` and `rationale` are LLM-produced (the agentic step, F4); everything else is tool-produced. The rationale is surfaced in the PR comment and DataHub doc to make the reasoning auditable.

---



## 9. Demo dataset (seed)

Minimum graph:

1. `raw.orders` (upstream) — columns include `user_id` / later `customer_id`
2. `staging.stg_orders` (dbt)
3. `marts.fct_orders` (dbt) — projects and joins on `user_id` (so `rewrite` has something real to change)
4. `ml.features_orders` (feature table) → `mlFeature` `user_id` → `mlModel churn_predictor` — **in MVP** (thin ML edge, not stretch)
5. Owners on each node for reviewer mapping

Breaking change for demo: rename `user_id` → `customer_id` on `raw.orders`. This fans out to a rewritten `fct_orders.sql` PR **and** a `cascade:retrain-suggested` tag on `churn_predictor` — one run, visible across dataset + ML.

---



## 10. Success metrics (hackathon)


| Signal                               | Pass bar                                                                      |
| ------------------------------------ | ----------------------------------------------------------------------------- |
| Judge understands in video           | Yes without reading code                                                      |
| Generated SQL is genuinely mergeable | `rewrite` output would merge with light review — not just a column-alias shim |
| Agentic reasoning is visible         | Strategy + rationale shown on camera; not obviously a template pipeline       |
| Write-back visible                   | Tag + doc on dataset **and** `retrain-suggested` on the model                 |
| Originality                          | Touches 3 categories in one run; clearly beyond “show me lineage”             |
| Works end-to-end                     | Golden-diff eval (F11) passes in CI                                           |
| Setup                                | README gets them running or `examples/` stand alone                           |


---



## 11. Out of scope

- Catching *silent* data-plane failures (frozen loads, freshness drift) — different problem, different lane (see §1 framing note)
- Guaranteeing semantic rename detection at 100% (heuristic-first, annotation confirms)
- Automatic merge without human review
- Replacing DataHub UI or Analytics Agent
- Production multi-tenant SaaS

---



## 12. Resolved decisions


| #   | Decision                                                                | Rationale                                                                       |
| --- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| 1   | Primary strategy = `rewrite` downstream SQL; `adapter_view` is fallback | Keeps the "code a team would merge" claim honest; avoids the shim-only trap     |
| 2   | LLM owns strategy + rewrite; deterministic parts are tools              | Makes it a real *agent* for The Agent Hackathon (§2.1)                          |
| 3   | Rename detection: **heuristic first**, annotation confirms/overrides    | Demo still shows the agent "figuring it out," not requiring a hand-written hint |
| 4   | ML edge (feature→model) is **in MVP**, kept thin                        | 3-category coverage in one run for low cost                                     |
| 5   | Golden-diff eval is **in MVP DoD**, not deferred                        | "Actually works end-to-end" is scored                                           |
| 6   | Snowflake-shaped URNs, mono-repo downstream folders                     | One platform string; cross-repo is Phase 6                                      |
| 7   | Record video against the **offline fixture path**                       | Live MCP loop too fragile to bet the recording on                               |


