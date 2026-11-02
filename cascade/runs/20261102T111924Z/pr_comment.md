## Cascade impact report

**What changed:** user_id to customer_id on `raw_orders`
**Downstream:** 3 models (high)
**Agent:** deterministic

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

**ML:** retrain suggested for `churn_predictor`

**Source:** `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)`
