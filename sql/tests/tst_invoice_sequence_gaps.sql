WITH base AS (
    SELECT DISTINCT
        "Kreditor" AS kreditor,
        TRY_CAST(REGEXP_REPLACE(CAST("Belegnummer" AS VARCHAR), '\\.0+$', '') AS BIGINT) AS belegnummer_num,
        REGEXP_REPLACE(CAST("Belegnummer" AS VARCHAR), '\\.0+$', '') AS belegnummer
    FROM main.fraud_1
    WHERE "Kreditor" IS NOT NULL
      AND TRY_CAST(REGEXP_REPLACE(CAST("Belegnummer" AS VARCHAR), '\\.0+$', '') AS BIGINT) IS NOT NULL
),
with_prev AS (
    SELECT
        kreditor,
        belegnummer,
        belegnummer_num,
        LAG(belegnummer_num) OVER (PARTITION BY kreditor ORDER BY belegnummer_num) AS previous_belegnummer_num
    FROM base
)
SELECT
    kreditor,
    belegnummer,
    CAST(previous_belegnummer_num AS VARCHAR) AS previous_belegnummer,
    (belegnummer_num - previous_belegnummer_num) AS sequence_gap
FROM with_prev
WHERE previous_belegnummer_num IS NOT NULL
  AND (belegnummer_num - previous_belegnummer_num) >= 10
ORDER BY sequence_gap DESC, kreditor, belegnummer_num;
