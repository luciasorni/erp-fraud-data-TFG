# Data Dictionary O2C

Generado automáticamente desde schema canónico + mapping O2C.

## Alcance

- Proceso: `O2C`
- Fuente: `ERP Fraud Data / raw_data`

## Tabla: `o2c_collection`

### `o2c_collection.amount_local_currency`

- `type`: `decimal(18,2)`
- `required`: `True`
- `process_step`: `collection`
- `cast`: `decimal(18,2)`
- `source_candidates`: `BSEG.DMBTR`
- `default`: `None`
- `description`: Campo canónico O2C 'amount_local_currency' de la entidad 'o2c_collection' en el paso de proceso 'collection'.

### `o2c_collection.baseline_date`

- `type`: `date`
- `required`: `False`
- `process_step`: `collection`
- `cast`: `date`
- `source_candidates`: `BSEG.ZFBDT`
- `default`: `None`
- `description`: Campo canónico O2C 'baseline_date' de la entidad 'o2c_collection' en el paso de proceso 'collection'.

### `o2c_collection.clearing_date`

- `type`: `date`
- `required`: `False`
- `process_step`: `collection`
- `cast`: `date`
- `source_candidates`: `BSEG.AUGDT`
- `default`: `None`
- `description`: Campo canónico O2C 'clearing_date' de la entidad 'o2c_collection' en el paso de proceso 'collection'.

### `o2c_collection.clearing_document_id`

- `type`: `string`
- `required`: `False`
- `process_step`: `collection`
- `cast`: `string`
- `source_candidates`: `BSEG.AUGBL`
- `default`: `None`
- `description`: Campo canónico O2C 'clearing_document_id' de la entidad 'o2c_collection' en el paso de proceso 'collection'.

### `o2c_collection.company_code`

- `type`: `string`
- `required`: `True`
- `process_step`: `collection`
- `cast`: `string`
- `source_candidates`: `BSEG.BUKRS`
- `default`: `None`
- `description`: Campo canónico O2C 'company_code' de la entidad 'o2c_collection' en el paso de proceso 'collection'.

### `o2c_collection.customer_id`

- `type`: `string`
- `required`: `True`
- `process_step`: `collection`
- `cast`: `string`
- `source_candidates`: `BSEG.KUNNR`
- `default`: `None`
- `description`: Campo canónico O2C 'customer_id' de la entidad 'o2c_collection' en el paso de proceso 'collection'.

### `o2c_collection.fiscal_year`

- `type`: `string`
- `required`: `True`
- `process_step`: `collection`
- `cast`: `string`
- `source_candidates`: `BSEG.GJAHR`
- `default`: `None`
- `description`: Campo canónico O2C 'fiscal_year' de la entidad 'o2c_collection' en el paso de proceso 'collection'.

### `o2c_collection.payment_terms`

- `type`: `string`
- `required`: `False`
- `process_step`: `collection`
- `cast`: `string`
- `source_candidates`: `BSEG.ZTERM`
- `default`: `None`
- `description`: Campo canónico O2C 'payment_terms' de la entidad 'o2c_collection' en el paso de proceso 'collection'.

### `o2c_collection.posting_date`

- `type`: `date`
- `required`: `False`
- `process_step`: `collection`
- `cast`: `date`
- `source_candidates`: `BKPF.BUDAT`
- `default`: `None`
- `description`: Campo canónico O2C 'posting_date' de la entidad 'o2c_collection' en el paso de proceso 'collection'.

### `o2c_collection.receivable_document_id`

- `type`: `string`
- `required`: `True`
- `process_step`: `collection`
- `cast`: `string`
- `source_candidates`: `BSEG.BELNR`
- `default`: `None`
- `description`: Campo canónico O2C 'receivable_document_id' de la entidad 'o2c_collection' en el paso de proceso 'collection'.

## Tabla: `o2c_customer`

### `o2c_customer.account_group`

- `type`: `string`
- `required`: `False`
- `process_step`: `master_data`
- `cast`: `string`
- `source_candidates`: `KNA1.KTOKD`
- `default`: `None`
- `description`: Campo canónico O2C 'account_group' de la entidad 'o2c_customer' en el paso de proceso 'master_data'.

### `o2c_customer.city`

- `type`: `string`
- `required`: `False`
- `process_step`: `master_data`
- `cast`: `string`
- `source_candidates`: `KNA1.ORT01`
- `default`: `None`
- `description`: Campo canónico O2C 'city' de la entidad 'o2c_customer' en el paso de proceso 'master_data'.

### `o2c_customer.country`

- `type`: `string`
- `required`: `False`
- `process_step`: `master_data`
- `cast`: `string`
- `source_candidates`: `KNA1.LAND1`
- `default`: `None`
- `description`: Campo canónico O2C 'country' de la entidad 'o2c_customer' en el paso de proceso 'master_data'.

### `o2c_customer.customer_id`

- `type`: `string`
- `required`: `True`
- `process_step`: `master_data`
- `cast`: `string`
- `source_candidates`: `KNA1.KUNNR`
- `default`: `None`
- `description`: Campo canónico O2C 'customer_id' de la entidad 'o2c_customer' en el paso de proceso 'master_data'.

### `o2c_customer.customer_name`

- `type`: `string`
- `required`: `True`
- `process_step`: `master_data`
- `cast`: `string`
- `source_candidates`: `KNA1.NAME1`
- `default`: `None`
- `description`: Campo canónico O2C 'customer_name' de la entidad 'o2c_customer' en el paso de proceso 'master_data'.

### `o2c_customer.dunning_procedure`

- `type`: `string`
- `required`: `False`
- `process_step`: `master_data`
- `cast`: `string`
- `source_candidates`: `KNB1.MAHNA`
- `default`: `None`
- `description`: Campo canónico O2C 'dunning_procedure' de la entidad 'o2c_customer' en el paso de proceso 'master_data'.

### `o2c_customer.payment_terms`

- `type`: `string`
- `required`: `False`
- `process_step`: `master_data`
- `cast`: `string`
- `source_candidates`: `KNB1.ZTERM`
- `default`: `None`
- `description`: Campo canónico O2C 'payment_terms' de la entidad 'o2c_customer' en el paso de proceso 'master_data'.

### `o2c_customer.reconciliation_account`

- `type`: `string`
- `required`: `False`
- `process_step`: `master_data`
- `cast`: `string`
- `source_candidates`: `KNB1.AKONT`
- `default`: `None`
- `description`: Campo canónico O2C 'reconciliation_account' de la entidad 'o2c_customer' en el paso de proceso 'master_data'.

## Tabla: `o2c_delivery`

### `o2c_delivery.delivered_quantity`

- `type`: `decimal(18,3)`
- `required`: `True`
- `process_step`: `delivery`
- `cast`: `decimal(18,3)`
- `source_candidates`: `LIPS.LFIMG`
- `default`: `None`
- `description`: Campo canónico O2C 'delivered_quantity' de la entidad 'o2c_delivery' en el paso de proceso 'delivery'.

### `o2c_delivery.delivery_date`

- `type`: `date`
- `required`: `False`
- `process_step`: `delivery`
- `cast`: `date`
- `source_candidates`: `LIKP.LFDAT`
- `default`: `None`
- `description`: Campo canónico O2C 'delivery_date' de la entidad 'o2c_delivery' en el paso de proceso 'delivery'.

### `o2c_delivery.delivery_id`

- `type`: `string`
- `required`: `True`
- `process_step`: `delivery`
- `cast`: `string`
- `source_candidates`: `LIPS.VBELN, LIKP.VBELN`
- `default`: `None`
- `description`: Campo canónico O2C 'delivery_id' de la entidad 'o2c_delivery' en el paso de proceso 'delivery'.

### `o2c_delivery.delivery_item_id`

- `type`: `string`
- `required`: `True`
- `process_step`: `delivery`
- `cast`: `string`
- `source_candidates`: `LIPS.POSNR`
- `default`: `None`
- `description`: Campo canónico O2C 'delivery_item_id' de la entidad 'o2c_delivery' en el paso de proceso 'delivery'.

### `o2c_delivery.goods_issue_date`

- `type`: `date`
- `required`: `False`
- `process_step`: `delivery`
- `cast`: `date`
- `source_candidates`: `LIKP.WADAT_IST`
- `default`: `None`
- `description`: Campo canónico O2C 'goods_issue_date' de la entidad 'o2c_delivery' en el paso de proceso 'delivery'.

### `o2c_delivery.material_id`

- `type`: `string`
- `required`: `False`
- `process_step`: `delivery`
- `cast`: `string`
- `source_candidates`: `LIPS.MATNR`
- `default`: `None`
- `description`: Campo canónico O2C 'material_id' de la entidad 'o2c_delivery' en el paso de proceso 'delivery'.

### `o2c_delivery.plant_id`

- `type`: `string`
- `required`: `False`
- `process_step`: `delivery`
- `cast`: `string`
- `source_candidates`: `LIPS.WERKS`
- `default`: `None`
- `description`: Campo canónico O2C 'plant_id' de la entidad 'o2c_delivery' en el paso de proceso 'delivery'.

### `o2c_delivery.reference_sales_order_id`

- `type`: `string`
- `required`: `True`
- `process_step`: `delivery`
- `cast`: `string`
- `source_candidates`: `LIPS.VGBEL`
- `default`: `None`
- `description`: Campo canónico O2C 'reference_sales_order_id' de la entidad 'o2c_delivery' en el paso de proceso 'delivery'.

### `o2c_delivery.reference_sales_order_item_id`

- `type`: `string`
- `required`: `True`
- `process_step`: `delivery`
- `cast`: `string`
- `source_candidates`: `LIPS.VGPOS`
- `default`: `None`
- `description`: Campo canónico O2C 'reference_sales_order_item_id' de la entidad 'o2c_delivery' en el paso de proceso 'delivery'.

### `o2c_delivery.ship_to_customer_id`

- `type`: `string`
- `required`: `False`
- `process_step`: `delivery`
- `cast`: `string`
- `source_candidates`: `LIKP.KUNNR`
- `default`: `None`
- `description`: Campo canónico O2C 'ship_to_customer_id' de la entidad 'o2c_delivery' en el paso de proceso 'delivery'.

## Tabla: `o2c_invoice`

### `o2c_invoice.accounting_document_id`

- `type`: `string`
- `required`: `True`
- `process_step`: `invoice`
- `cast`: `string`
- `source_candidates`: `BKPF.BELNR, BSEG.BELNR`
- `default`: `None`
- `description`: Campo canónico O2C 'accounting_document_id' de la entidad 'o2c_invoice' en el paso de proceso 'invoice'.

### `o2c_invoice.amount_local_currency`

- `type`: `decimal(18,2)`
- `required`: `True`
- `process_step`: `invoice`
- `cast`: `decimal(18,2)`
- `source_candidates`: `BSEG.DMBTR`
- `default`: `None`
- `description`: Campo canónico O2C 'amount_local_currency' de la entidad 'o2c_invoice' en el paso de proceso 'invoice'.

### `o2c_invoice.baseline_date`

- `type`: `date`
- `required`: `False`
- `process_step`: `invoice`
- `cast`: `date`
- `source_candidates`: `BSEG.ZFBDT`
- `default`: `None`
- `description`: Campo canónico O2C 'baseline_date' de la entidad 'o2c_invoice' en el paso de proceso 'invoice'.

### `o2c_invoice.clearing_date`

- `type`: `date`
- `required`: `False`
- `process_step`: `invoice`
- `cast`: `date`
- `source_candidates`: `BSEG.AUGDT`
- `default`: `None`
- `description`: Campo canónico O2C 'clearing_date' de la entidad 'o2c_invoice' en el paso de proceso 'invoice'.

### `o2c_invoice.clearing_document_id`

- `type`: `string`
- `required`: `False`
- `process_step`: `invoice`
- `cast`: `string`
- `source_candidates`: `BSEG.AUGBL`
- `default`: `None`
- `description`: Campo canónico O2C 'clearing_document_id' de la entidad 'o2c_invoice' en el paso de proceso 'invoice'.

### `o2c_invoice.company_code`

- `type`: `string`
- `required`: `True`
- `process_step`: `invoice`
- `cast`: `string`
- `source_candidates`: `BKPF.BUKRS, BSEG.BUKRS`
- `default`: `None`
- `description`: Campo canónico O2C 'company_code' de la entidad 'o2c_invoice' en el paso de proceso 'invoice'.

### `o2c_invoice.customer_or_account_id`

- `type`: `string`
- `required`: `True`
- `process_step`: `invoice`
- `cast`: `string`
- `source_candidates`: `BSEG.KUNNR, BSEG.HKONT`
- `default`: `None`
- `description`: Campo canónico O2C 'customer_or_account_id' de la entidad 'o2c_invoice' en el paso de proceso 'invoice'.

### `o2c_invoice.debit_credit_indicator`

- `type`: `string`
- `required`: `False`
- `process_step`: `invoice`
- `cast`: `string`
- `source_candidates`: `BSEG.SHKZG`
- `default`: `None`
- `description`: Campo canónico O2C 'debit_credit_indicator' de la entidad 'o2c_invoice' en el paso de proceso 'invoice'.

### `o2c_invoice.document_currency_amount`

- `type`: `decimal(18,2)`
- `required`: `False`
- `process_step`: `invoice`
- `cast`: `decimal(18,2)`
- `source_candidates`: `BSEG.WRBTR`
- `default`: `None`
- `description`: Campo canónico O2C 'document_currency_amount' de la entidad 'o2c_invoice' en el paso de proceso 'invoice'.

### `o2c_invoice.fiscal_year`

- `type`: `string`
- `required`: `True`
- `process_step`: `invoice`
- `cast`: `string`
- `source_candidates`: `BKPF.GJAHR, BSEG.GJAHR`
- `default`: `None`
- `description`: Campo canónico O2C 'fiscal_year' de la entidad 'o2c_invoice' en el paso de proceso 'invoice'.

### `o2c_invoice.posting_date`

- `type`: `date`
- `required`: `True`
- `process_step`: `invoice`
- `cast`: `date`
- `source_candidates`: `BKPF.BUDAT`
- `default`: `None`
- `description`: Campo canónico O2C 'posting_date' de la entidad 'o2c_invoice' en el paso de proceso 'invoice'.

### `o2c_invoice.reference_delivery_id`

- `type`: `string`
- `required`: `False`
- `process_step`: `invoice`
- `cast`: `string`
- `source_candidates`: `LIPS.VBELN`
- `default`: `None`
- `description`: Campo canónico O2C 'reference_delivery_id' de la entidad 'o2c_invoice' en el paso de proceso 'invoice'.

## Tabla: `o2c_order`

### `o2c_order.condition_amount`

- `type`: `decimal(18,2)`
- `required`: `False`
- `process_step`: `sales_order`
- `cast`: `decimal(18,2)`
- `source_candidates`: `KONV.KWERT`
- `default`: `None`
- `description`: Campo canónico O2C 'condition_amount' de la entidad 'o2c_order' en el paso de proceso 'sales_order'.

### `o2c_order.customer_group`

- `type`: `string`
- `required`: `False`
- `process_step`: `sales_order`
- `cast`: `string`
- `source_candidates`: `KNA1.KDGRP`
- `default`: `None`
- `description`: Campo canónico O2C 'customer_group' de la entidad 'o2c_order' en el paso de proceso 'sales_order'.

### `o2c_order.customer_id`

- `type`: `string`
- `required`: `True`
- `process_step`: `sales_order`
- `cast`: `string`
- `source_candidates`: `VBAK.KUNNR, VBPA.KUNNR`
- `default`: `None`
- `description`: Campo canónico O2C 'customer_id' de la entidad 'o2c_order' en el paso de proceso 'sales_order'.

### `o2c_order.distribution_channel`

- `type`: `string`
- `required`: `False`
- `process_step`: `sales_order`
- `cast`: `string`
- `source_candidates`: `VBAK.VTWEG`
- `default`: `None`
- `description`: Campo canónico O2C 'distribution_channel' de la entidad 'o2c_order' en el paso de proceso 'sales_order'.

### `o2c_order.division`

- `type`: `string`
- `required`: `False`
- `process_step`: `sales_order`
- `cast`: `string`
- `source_candidates`: `VBAK.SPART`
- `default`: `None`
- `description`: Campo canónico O2C 'division' de la entidad 'o2c_order' en el paso de proceso 'sales_order'.

### `o2c_order.item_net_price`

- `type`: `decimal(18,4)`
- `required`: `False`
- `process_step`: `sales_order`
- `cast`: `decimal(18,4)`
- `source_candidates`: `VBAP.NETPR`
- `default`: `None`
- `description`: Campo canónico O2C 'item_net_price' de la entidad 'o2c_order' en el paso de proceso 'sales_order'.

### `o2c_order.material_id`

- `type`: `string`
- `required`: `False`
- `process_step`: `sales_order`
- `cast`: `string`
- `source_candidates`: `VBAP.MATNR`
- `default`: `None`
- `description`: Campo canónico O2C 'material_id' de la entidad 'o2c_order' en el paso de proceso 'sales_order'.

### `o2c_order.net_amount`

- `type`: `decimal(18,2)`
- `required`: `True`
- `process_step`: `sales_order`
- `cast`: `decimal(18,2)`
- `source_candidates`: `VBAP.NETWR`
- `default`: `None`
- `description`: Campo canónico O2C 'net_amount' de la entidad 'o2c_order' en el paso de proceso 'sales_order'.

### `o2c_order.order_created_date`

- `type`: `date`
- `required`: `True`
- `process_step`: `sales_order`
- `cast`: `date`
- `source_candidates`: `VBAK.ERDAT`
- `default`: `None`
- `description`: Campo canónico O2C 'order_created_date' de la entidad 'o2c_order' en el paso de proceso 'sales_order'.

### `o2c_order.ordered_quantity`

- `type`: `decimal(18,3)`
- `required`: `False`
- `process_step`: `sales_order`
- `cast`: `decimal(18,3)`
- `source_candidates`: `VBAP.KWMENG`
- `default`: `None`
- `description`: Campo canónico O2C 'ordered_quantity' de la entidad 'o2c_order' en el paso de proceso 'sales_order'.

### `o2c_order.sales_order_id`

- `type`: `string`
- `required`: `True`
- `process_step`: `sales_order`
- `cast`: `string`
- `source_candidates`: `VBAK.VBELN, VBAP.VBELN`
- `default`: `None`
- `description`: Campo canónico O2C 'sales_order_id' de la entidad 'o2c_order' en el paso de proceso 'sales_order'.

### `o2c_order.sales_order_item_id`

- `type`: `string`
- `required`: `True`
- `process_step`: `sales_order`
- `cast`: `string`
- `source_candidates`: `VBAP.POSNR`
- `default`: `None`
- `description`: Campo canónico O2C 'sales_order_item_id' de la entidad 'o2c_order' en el paso de proceso 'sales_order'.

### `o2c_order.sales_org`

- `type`: `string`
- `required`: `False`
- `process_step`: `sales_order`
- `cast`: `string`
- `source_candidates`: `VBAK.VKORG`
- `default`: `None`
- `description`: Campo canónico O2C 'sales_org' de la entidad 'o2c_order' en el paso de proceso 'sales_order'.
