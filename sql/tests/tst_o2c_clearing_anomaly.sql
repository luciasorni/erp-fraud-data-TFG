SELECT
    company_code,
    receivable_document_id,
    fiscal_year,
    customer_id,
    amount_local_currency,
    baseline_date,
    clearing_date,
    clearing_document_id
FROM "o2c"."o2c_collection"
WHERE (clearing_date IS NOT NULL AND baseline_date IS NOT NULL AND clearing_date < baseline_date)
   OR (clearing_document_id IS NULL AND amount_local_currency IS NOT NULL AND amount_local_currency > 10000)
ORDER BY company_code, receivable_document_id, fiscal_year
LIMIT 1000;
