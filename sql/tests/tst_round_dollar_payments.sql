SELECT
    "Kreditor" AS kreditor,
    "Belegnummer" AS belegnummer,
    TRY_CAST("Betrag" AS DOUBLE) AS betrag,
    CASE
        WHEN ABS(TRY_CAST("Betrag" AS DOUBLE) - ROUND(TRY_CAST("Betrag" AS DOUBLE), 0)) < 1e-9 THEN TRUE
        ELSE FALSE
    END AS is_round_amount
FROM main.fraud_1
WHERE TRY_CAST("Betrag" AS DOUBLE) IS NOT NULL
  AND ABS(TRY_CAST("Betrag" AS DOUBLE) - ROUND(TRY_CAST("Betrag" AS DOUBLE), 0)) < 1e-9
ORDER BY betrag DESC, kreditor, belegnummer;
