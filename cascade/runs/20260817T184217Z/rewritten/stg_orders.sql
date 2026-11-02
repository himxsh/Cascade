-- Analysts: do not drop customer_id until marts migrate.
-- event_name = 'customer_id' is a string, not a column.

WITH src AS (
    SELECT
        o.order_id,
        o.customer_id,
        o."USER_ID" AS user_id_quoted,
        o.amount,
        o.payload:customer_id::string AS payload_user,
        o.user_id_hash
    FROM analytics.raw_orders AS o
)

SELECT * FROM src
WHERE amount > 0
  AND 'customer_id' IS NOT NULL
