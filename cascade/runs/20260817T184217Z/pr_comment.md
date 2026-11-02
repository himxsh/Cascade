## Cascade impact report

**What changed:** user_id to customer_id on `raw_orders`
**Downstream:** 11 models (high)
**Agent:** deterministic

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

Cascade opened (or will open) a remediation PR with the SQL fix.

**ML:** retrain suggested for `churn_predictor`

**Source:** `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)`
