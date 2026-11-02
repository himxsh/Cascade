SELECT
    customer_id,
    COUNT(*) AS order_count,
    SUM(amount) AS total_amount
FROM analytics.fct_orders
GROUP BY 1
