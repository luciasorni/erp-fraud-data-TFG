SELECT
    "Kreditor" AS kreditor,
    "Belegnummer" AS belegnummer,
    CAST("Sachkonto" AS VARCHAR) AS sachkonto,
    CAST("Soll/Haben-Kennz_" AS VARCHAR) AS soll_haben_kennz,
    TRY_CAST("Betrag" AS DOUBLE) AS betrag,
    CASE
        WHEN ABS(TRY_CAST("Betrag" AS DOUBLE) - ROUND(TRY_CAST("Betrag" AS DOUBLE), 0)) < 1e-9 THEN TRUE
        ELSE FALSE
    END AS is_round_amount,
    CASE
        WHEN MOD(CAST(ROUND(TRY_CAST("Betrag" AS DOUBLE), 0) AS BIGINT), 2) = 0 THEN TRUE
        ELSE FALSE
    END AS is_even_amount
FROM main.fraud_1
WHERE TRY_CAST("Betrag" AS DOUBLE) IS NOT NULL
  AND ABS(TRY_CAST("Betrag" AS DOUBLE)) >= 10000
  AND ABS(TRY_CAST("Betrag" AS DOUBLE) - ROUND(TRY_CAST("Betrag" AS DOUBLE), 0)) < 1e-9
  AND MOD(CAST(ROUND(TRY_CAST("Betrag" AS DOUBLE), 0) AS BIGINT), 2) = 0
ORDER BY ABS(betrag) DESC, kreditor, belegnummer;
