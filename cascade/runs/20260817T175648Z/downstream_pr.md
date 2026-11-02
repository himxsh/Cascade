# Fix 3 downstream models after user_id → customer_id

A breaking schema change on **raw_orders** (user_id to customer_id) would break **3** downstream models.
This PR applies Cascade's rewrite so those models keep working.

- **Severity:** high
- **Agent:** deterministic

## What could break

```mermaid
flowchart LR
  s_raw_orders["raw_orders: user_id to customer_id"]
  d0_stg_orders["stg_orders"]
  s_raw_orders --> d0_stg_orders
  d1_fct_orders["fct_orders"]
  s_raw_orders --> d1_fct_orders
  d2_features_orders["features_orders"]
  s_raw_orders --> d2_features_orders
```

## How Cascade fixed it

```mermaid
flowchart TD
  change["user_id to customer_id"]
  blast["3 downstream models"]
  change --> blast
  r0["stg_orders: adapter_view (deterministic)"]
  blast --> r0
  r1["fct_orders: rewrite (deterministic)"]
  blast --> r1
  r2["features_orders: adapter_view (deterministic)"]
  blast --> r2
```

## Files in this PR

- `/Users/himeshjain/Desktop/Hackathons/Cascade/examples/models/fct_orders.sql` — rewrite (deterministic) — downstream SQL fct_orders.sql references user_id in SELECT/JOIN; rewriting to customer_id to match upstream schema change

## Other actions

- **adapter_view** `stg_orders` — no SQL model found for downstream node; recommend adapter view to alias user_id->customer_id while downstream migrates
- **adapter_view** `features_orders` — no SQL model found for downstream node; recommend adapter view to alias user_id->customer_id while downstream migrates

<details>
<summary>Details (URNs, owners, ML)</summary>

**Source:** `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)`

- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.stg_orders,PROD)` — owners: urn:li:corpuser:alice
- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.fct_orders,PROD)` — owners: urn:li:corpuser:alice
- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.features_orders,PROD)` — owners: urn:li:corpuser:bob
- ML `urn:li:mlModel:(urn:li:dataPlatform:snowflake,churn_predictor,PROD)` via `user_id` → `retrain-suggested`

</details>

<!-- cascade:source_urn=urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD) -->

## Suggested reviewers

- @alice
- @bob
