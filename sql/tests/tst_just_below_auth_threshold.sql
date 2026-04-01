WITH thresholds AS (
    SELECT * FROM (VALUES
        (100.0),
        (500.0),
        (1000.0),
        (5000.0),
        (10000.0)
    ) t(threshold_value)
),
base AS (
    SELECT
        "Kreditor" AS kreditor,
        "Belegnummer" AS belegnummer,
        TRY_CAST("Betrag" AS DOUBLE) AS betrag
    FROM main.fraud_1
    WHERE TRY_CAST("Betrag" AS DOUBLE) IS NOT NULL
),
matches AS (
    SELECT
        b.kreditor,
        b.belegnummer,
        b.betrag,
        t.threshold_value AS threshold,
        (t.threshold_value - b.betrag) AS threshold_gap,
        ROW_NUMBER() OVER (
            PARTITION BY b.kreditor, b.belegnummer, b.betrag
            ORDER BY t.threshold_value
        ) AS rn
    FROM base b
    JOIN thresholds t
      ON b.betrag < t.threshold_value
     AND b.betrag >= t.threshold_value * 0.98
)
SELECT
    kreditor,
    belegnummer,
    betrag,
    threshold,
    threshold_gap
FROM matches
WHERE rn = 1
ORDER BY threshold_gap ASC, betrag DESC, kreditor, belegnummer;
