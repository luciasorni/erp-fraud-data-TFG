SELECT
    delivery_id,
    delivery_item_id,
    reference_sales_order_id,
    reference_sales_order_item_id,
    delivered_quantity
FROM "o2c"."o2c_delivery"
WHERE TRY_CAST(delivered_quantity AS DOUBLE) IS NOT NULL
  AND TRY_CAST(delivered_quantity AS DOUBLE) < 0
ORDER BY delivered_quantity ASC, delivery_id, delivery_item_id;
