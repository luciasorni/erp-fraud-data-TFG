WITH base AS (
    SELECT
        "Kreditor" AS kreditor,
        "Belegnummer" AS belegnummer,
        TRY_CAST("Betrag" AS DOUBLE) AS betrag,
        TRIM(CAST("Erfassungsuhrzeit" AS VARCHAR)) AS erfassungsuhrzeit
    FROM main.fraud_1
    WHERE "Erfassungsuhrzeit" IS NOT NULL
),
parsed AS (
    SELECT
        kreditor,
        belegnummer,
        betrag,
        erfassungsuhrzeit,
        TRY_CAST(SPLIT_PART(erfassungsuhrzeit, ':', 1) AS INTEGER) AS posting_hour
    FROM base
    WHERE REGEXP_MATCHES(erfassungsuhrzeit, '^([01][0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?$')
)
SELECT
    kreditor,
    belegnummer,
    betrag,
    erfassungsuhrzeit,
    posting_hour,
    CASE
        WHEN posting_hour < 6 THEN 'night'
        WHEN posting_hour >= 22 THEN 'late_evening'
        ELSE 'business_hours'
    END AS unusual_window
FROM parsed
WHERE posting_hour < 6 OR posting_hour >= 22
ORDER BY posting_hour ASC, kreditor, belegnummer;
