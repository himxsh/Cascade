SELECT
    o.order_id,
    o.customer_id,
    c.customer_id AS login_user_id,
    c.customer_id,
    o.amount
FROM analytics.fct_orders AS o
INNER JOIN analytics.dim_customers AS c
    ON o.customer_id = c.customer_id
