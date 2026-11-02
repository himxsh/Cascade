# Cascade: remediate downstream schema break

## Cascade impact report

**Source:** `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD)`
**Severity:** `high`

### Schema changes

- `FIELD_RENAMED`: `user_id` → `customer_id` (detected_by=heuristic)

### Blast radius

- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.stg_orders,PROD)` — owners: urn:li:corpuser:alice
- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.fct_orders,PROD)` — owners: urn:li:corpuser:alice
- `urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.features_orders,PROD)` — owners: urn:li:corpuser:bob

### Agent remediations

- **adapter_view** (`urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.stg_orders,PROD)`)
  - _no SQL model found for downstream node; recommend adapter view to alias user_id->customer_id while downstream migrates_
- **rewrite** (`/Users/himeshjain/Desktop/Hackathons/Cascade/examples/models/fct_orders.sql`)
  - _downstream SQL fct_orders.sql references user_id in SELECT/JOIN; rewriting to customer_id to match upstream schema change_
- **adapter_view** (`urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.features_orders,PROD)`)
  - _no SQL model found for downstream node; recommend adapter view to alias user_id->customer_id while downstream migrates_

### ML impact

- `urn:li:mlModel:(urn:li:dataPlatform:snowflake,churn_predictor,PROD)` via `user_id` → `retrain-suggested`

<!-- cascade:source_urn=urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.raw_orders,PROD) -->

## Suggested reviewers

- @alice
- @bob

## Patch

```diff
--- a/fct_orders.sql
+++ b/fct_orders.sql
@@ -1,5 +1,5 @@
 SELECT
     order_id,
-    user_id,
+    customer_id,
     amount
 FROM analytics.raw_orders
```
