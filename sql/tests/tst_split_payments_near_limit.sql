WITH base AS (
    SELECT
        "Kreditor" AS kreditor,
        "Belegnummer" AS belegnummer,
        "Position" AS position,
        TRY_CAST("Betrag" AS DOUBLE) AS betrag
    FROM main.fraud_1
    WHERE "Kreditor" IS NOT NULL
      AND "Belegnummer" IS NOT NULL
      AND TRY_CAST("Betrag" AS DOUBLE) IS NOT NULL
),
agg AS (
    SELECT
        kreditor,
        belegnummer,
        COUNT(*) AS line_count,
        SUM(betrag) AS total_betrag,
        MAX(betrag) AS max_line_betrag
    FROM base
    GROUP BY 1, 2
)
SELECT
    kreditor,
    belegnummer,
    line_count,
    total_betrag,
    max_line_betrag,
    1000.0 AS threshold
FROM agg
WHERE line_count > 1
  AND max_line_betrag < 1000.0
  AND total_betrag >= 1000.0
ORDER BY total_betrag DESC, line_count DESC, kreditor, belegnummer;
