SELECT
    d.delivery_id,
    d.delivery_item_id,
    d.reference_sales_order_id,
    d.reference_sales_order_item_id,
    d.delivered_quantity,
    o.ordered_quantity,
    ABS(COALESCE(d.delivered_quantity, 0) - COALESCE(o.ordered_quantity, 0)) AS qty_gap
FROM "o2c"."o2c_delivery" d
LEFT JOIN "o2c"."o2c_order" o
  ON o.sales_order_id = d.reference_sales_order_id
 AND o.sales_order_item_id = d.reference_sales_order_item_id
WHERE o.sales_order_id IS NOT NULL
  AND ABS(COALESCE(d.delivered_quantity, 0) - COALESCE(o.ordered_quantity, 0)) > 0.0001
ORDER BY qty_gap DESC, d.delivery_id, d.delivery_item_id
LIMIT 1000;
