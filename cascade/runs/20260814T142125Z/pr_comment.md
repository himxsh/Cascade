## Cascade impact report

**What changed:** user_id to customer_id on `raw_orders`
**Downstream:** 3 models (high)
**Agent:** deterministic

```mermaid
flowchart LR
  raw_orders["raw_orders: user_id to customer_id"]
  stg_orders["stg_orders"]
  raw_orders --> stg_orders
  fct_orders["fct_orders"]
  raw_orders --> fct_orders
  features_orders["features_orders"]
  raw_orders --> features_orders
```

Cascade opened (or will open) a remediation PR with the SQL fix.

**ML:** retrain suggested for `churn_predictor`

**Source:** `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)`
