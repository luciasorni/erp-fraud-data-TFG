SELECT
    sales_order_id,
    sales_order_item_id,
    customer_id,
    net_amount,
    condition_amount,
    ABS(condition_amount) / NULLIF(ABS(net_amount), 0) AS discount_ratio
FROM "o2c"."o2c_order"
WHERE net_amount IS NOT NULL
  AND net_amount <> 0
  AND condition_amount IS NOT NULL
  AND ABS(condition_amount) / ABS(net_amount) > 0.30
ORDER BY discount_ratio DESC, customer_id, sales_order_id, sales_order_item_id
LIMIT 1000;
