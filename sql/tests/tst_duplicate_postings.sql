SELECT
    "Kreditor" AS kreditor,
    "Belegnummer" AS belegnummer,
    "Position" AS position,
    "Betrag" AS betrag,
    COUNT(*) AS duplicate_count
FROM main.fraud_1
GROUP BY 1, 2, 3, 4
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, kreditor, belegnummer, position;

