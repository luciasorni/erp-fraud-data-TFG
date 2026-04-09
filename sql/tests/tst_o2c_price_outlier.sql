WITH stats AS (
    SELECT
        customer_id,
        AVG(net_amount) AS mean_amount,
        STDDEV_SAMP(net_amount) AS std_amount,
        COUNT(*) AS n_rows
    FROM "o2c"."o2c_order"
    WHERE net_amount IS NOT NULL
    GROUP BY 1
    HAVING COUNT(*) >= 3 AND STDDEV_SAMP(net_amount) > 0
)
SELECT
    o.sales_order_id,
    o.sales_order_item_id,
    o.customer_id,
    o.net_amount,
    s.mean_amount,
    s.std_amount,
    ABS((o.net_amount - s.mean_amount) / s.std_amount) AS z_score
FROM "o2c"."o2c_order" o
JOIN stats s USING (customer_id)
WHERE ABS((o.net_amount - s.mean_amount) / s.std_amount) >= 1.0
ORDER BY z_score DESC, o.customer_id, o.sales_order_id, o.sales_order_item_id
LIMIT 1000;
