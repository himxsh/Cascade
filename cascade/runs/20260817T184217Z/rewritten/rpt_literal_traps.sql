-- Column lineage claims this consumes raw_orders.customer_id.
-- The SQL never selects that column; it only mentions the token in prose.
SELECT
    'customer_id' AS note
-- backlog: migrate customer_id dashboards
