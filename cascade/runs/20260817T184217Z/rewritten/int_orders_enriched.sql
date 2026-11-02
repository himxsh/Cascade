-- Mean join: orders.customer_id (buyer) = customers.customer_id (login). After a correct
-- orders rename this ON should become o.customer_id = c.customer_id, and c.customer_id
-- (login) must stay.
WITH base AS (
    SELECT
        o.order_id,
        o.customer_id,
        c.email
    FROM analytics.stg_orders AS o
    LEFT JOIN analytics.stg_customers AS c
        ON o.customer_id = c.customer_id
)
SELECT * FROM base
