WITH base AS (
    SELECT
        "Kreditor" AS kreditor,
        TRY_CAST("Betrag" AS DOUBLE) AS betrag,
        "Transaktionsart" AS transaktionsart
    FROM main.fraud_1
    WHERE "Kreditor" IS NOT NULL
      AND TRY_CAST("Betrag" AS DOUBLE) IS NOT NULL
),
stats AS (
    SELECT
        kreditor,
        COUNT(*) AS n_rows,
        AVG(betrag) AS mean_betrag,
        STDDEV_SAMP(betrag) AS std_betrag
    FROM base
    GROUP BY 1
    HAVING COUNT(*) >= 5
)
SELECT
    b.kreditor,
    b.transaktionsart,
    b.betrag,
    s.n_rows,
    s.mean_betrag,
    s.std_betrag,
    ABS((b.betrag - s.mean_betrag) / NULLIF(s.std_betrag, 0)) AS z_score
FROM base b
JOIN stats s USING (kreditor)
WHERE s.std_betrag IS NOT NULL
  AND s.std_betrag > 0
  AND ABS((b.betrag - s.mean_betrag) / s.std_betrag) >= 3.0
ORDER BY z_score DESC, b.kreditor;

