# Fix 11 downstream models after user_id → customer_id

A breaking schema change on **raw_orders** (user_id to customer_id) would break **11** downstream models.
This PR applies Cascade's rewrite so those models keep working.

- **Severity:** high
- **Agent:** deterministic

## What could break

```mermaid
flowchart LR
  s_raw_orders["raw_orders: user_id to customer_id"]
  d0_stg_orders["stg_orders"]
  s_raw_orders --> d0_stg_orders
  d1_stg_orders_star["stg_orders_star"]
  s_raw_orders --> d1_stg_orders_star
  d2_stg_payments["stg_payments"]
  s_raw_orders --> d2_stg_payments
  d3_orphan_legacy_orders["orphan_legacy_orders"]
  s_raw_orders --> d3_orphan_legacy_orders
  d4_rpt_literal_traps["rpt_literal_traps"]
  s_raw_orders --> d4_rpt_literal_traps
  d5_int_orders_enriched["int_orders_enriched"]
  s_raw_orders --> d5_int_orders_enriched
  d6_int_union_identities["int_union_identities"]
  s_raw_orders --> d6_int_union_identities
  d7_fct_orders["fct_orders"]
  s_raw_orders --> d7_fct_orders
  d8_mart_revenue["mart_revenue"]
  s_raw_orders --> d8_mart_revenue
  d9_features_orders["features_orders"]
  s_raw_orders --> d9_features_orders
  d10_bq_fct_orders["bq_fct_orders"]
  s_raw_orders --> d10_bq_fct_orders
```

## How Cascade fixed it

```mermaid
flowchart TD
  change["user_id to customer_id"]
  blast["11 downstream models"]
  change --> blast
  r0["stg_orders: rewrite (deterministic)"]
  blast --> r0
  r1["stg_payments: rewrite (deterministic)"]
  blast --> r1
  r2["orphan_legacy_orders: adapter_view (deterministic)"]
  blast --> r2
  r3["rpt_literal_traps: rewrite (deterministic)"]
  blast --> r3
  r4["int_orders_enriched: rewrite (deterministic)"]
  blast --> r4
  r5["int_union_identities: adapter_view (deterministic)"]
  blast --> r5
  r6["fct_orders: rewrite (deterministic)"]
  blast --> r6
  r7["mart_revenue: rewrite (deterministic)"]
  blast --> r7
  r8["features_orders: rewrite (deterministic)"]
  blast --> r8
  r9["bq_fct_orders: adapter_view (deterministic)"]
  blast --> r9
```

## Files in this PR

- `examples/mean/stg_orders.sql` — rewrite (deterministic) — downstream SQL stg_orders.sql references user_id in SELECT/JOIN; rewriting to customer_id to match upstream schema change
- `examples/mean/stg_payments.sql` — rewrite (deterministic) — downstream SQL stg_payments.sql references user_id in SELECT/JOIN; rewriting to customer_id to match upstream schema change
- `examples/mean/rpt_literal_traps.sql` — rewrite (deterministic) — downstream SQL rpt_literal_traps.sql references user_id in SELECT/JOIN; rewriting to customer_id to match upstream schema change
- `examples/mean/int_orders_enriched.sql` — rewrite (deterministic) — downstream SQL int_orders_enriched.sql references user_id in SELECT/JOIN; rewriting to customer_id to match upstream schema change
- `examples/mean/fct_orders.sql` — rewrite (deterministic) — downstream SQL fct_orders.sql references user_id in SELECT/JOIN; rewriting to customer_id to match upstream schema change
- `examples/mean/mart_revenue.sql` — rewrite (deterministic) — downstream SQL mart_revenue.sql references user_id in SELECT/JOIN; rewriting to customer_id to match upstream schema change
- `examples/mean/features_orders.sql` — rewrite (deterministic) — downstream SQL features_orders.sql references user_id in SELECT/JOIN; rewriting to customer_id to match upstream schema change

## Other actions

- **adapter_view** `orphan_legacy_orders` — no SQL model found for downstream node; recommend adapter view to alias user_id->customer_id while downstream migrates
- **adapter_view** `int_union_identities` — rewrite of user_id->customer_id in int_union_identities.sql failed schema gate; falling back to adapter view
- **adapter_view** `bq_fct_orders` — rewrite of user_id->customer_id in bq_fct_orders.sql failed schema gate; falling back to adapter view

<details>
<summary>Details (URNs, owners, ML)</summary>

**Source:** `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)`

- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.stg_orders,PROD)` — owners: urn:li:corpuser:alice
- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.stg_orders_star,PROD)` — owners: urn:li:corpuser:alice
- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.stg_payments,PROD)` — owners: urn:li:corpuser:alice
- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.orphan_legacy_orders,PROD)` — owners: urn:li:corpuser:alice
- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.rpt_literal_traps,PROD)` — owners: urn:li:corpuser:eve
- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.int_orders_enriched,PROD)` — owners: urn:li:corpuser:bob
- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.int_union_identities,PROD)` — owners: urn:li:corpuser:eve
- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.fct_orders,PROD)` — owners: urn:li:corpuser:bob
- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.mart_revenue,PROD)` — owners: urn:li:corpuser:bob, urn:li:corpuser:carol
- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.features_orders,PROD)` — owners: urn:li:corpuser:ml-platform
- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.bq_fct_orders,PROD)` — owners: urn:li:corpuser:bob
- ML `urn:li:mlModel:(urn:li:dataPlatform:snowflake,churn_predictor,PROD)` via `user_id` → `retrain-suggested`

</details>

<!-- cascade:source_urn=urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD) -->

## Suggested reviewers

- @alice
- @eve
- @bob
- @carol
- @ml-platform
