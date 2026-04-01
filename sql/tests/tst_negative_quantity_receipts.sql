SELECT
    "Kreditor" AS kreditor,
    "Belegnummer" AS belegnummer,
    "Material" AS material,
    TRY_CAST("Menge" AS DOUBLE) AS menge
FROM main.fraud_1
WHERE TRY_CAST("Menge" AS DOUBLE) < 0
ORDER BY menge ASC, kreditor, belegnummer;
