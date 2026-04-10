WITH numeric_docs AS (
    SELECT
        company_code,
        accounting_document_id,
        fiscal_year,
        customer_or_account_id,
        posting_date,
        TRY_CAST(regexp_replace(accounting_document_id, '[^0-9]', '', 'g') AS BIGINT) AS accounting_document_num
    FROM "o2c"."o2c_invoice"
    WHERE accounting_document_id IS NOT NULL
      AND customer_or_account_id IS NOT NULL
),
ordered AS (
    SELECT
        company_code,
        accounting_document_id,
        fiscal_year,
        customer_or_account_id,
        posting_date,
        accounting_document_num,
        LAG(accounting_document_num) OVER (
            PARTITION BY customer_or_account_id
            ORDER BY accounting_document_num
        ) AS prev_document_num
    FROM numeric_docs
    WHERE accounting_document_num IS NOT NULL
)
SELECT
    company_code,
    accounting_document_id,
    fiscal_year,
    customer_or_account_id,
    posting_date,
    accounting_document_num,
    prev_document_num,
    accounting_document_num - prev_document_num AS document_gap
FROM ordered
WHERE prev_document_num IS NOT NULL
  AND accounting_document_num - prev_document_num > 100
ORDER BY document_gap DESC, customer_or_account_id, company_code, accounting_document_id
LIMIT 1000;
