WITH stats AS (
    SELECT
        customer_or_account_id,
        AVG(ABS(amount_local_currency)) AS mean_amount,
        STDDEV_SAMP(ABS(amount_local_currency)) AS std_amount,
        COUNT(*) AS n_rows
    FROM "o2c"."o2c_invoice"
    WHERE amount_local_currency IS NOT NULL
      AND customer_or_account_id IS NOT NULL
    GROUP BY 1
    HAVING COUNT(*) >= 3 AND STDDEV_SAMP(ABS(amount_local_currency)) > 0
)
SELECT
    i.company_code,
    i.accounting_document_id,
    i.fiscal_year,
    i.customer_or_account_id,
    i.posting_date,
    i.amount_local_currency,
    s.mean_amount,
    s.std_amount,
    ABS((ABS(i.amount_local_currency) - s.mean_amount) / s.std_amount) AS z_score
FROM "o2c"."o2c_invoice" i
JOIN stats s USING (customer_or_account_id)
WHERE ABS((ABS(i.amount_local_currency) - s.mean_amount) / s.std_amount) >= 1.0
ORDER BY z_score DESC, i.customer_or_account_id, i.company_code, i.accounting_document_id
LIMIT 1000;
