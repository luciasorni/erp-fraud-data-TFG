SELECT
    "Kreditor" AS kreditor,
    "Belegnummer" AS belegnummer,
    "Position" AS position,
    "Material" AS material,
    COUNT(*) AS duplicate_count
FROM main.fraud_1
WHERE "Material" IS NOT NULL
GROUP BY 1, 2, 3, 4
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, kreditor, belegnummer, position, material;
