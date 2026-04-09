# RF13-P2P — Matriz `hipótesis -> tests -> evidencias`

## 1) Objetivo

Alinear P2P al mismo patrón de gobernanza que O2C:

1. hipótesis explícitas por riesgo,
2. vínculo directo a `test_id` ejecutable,
3. columnas de evidencia y business keys trazables.

## 2) Artefactos

- Matriz CSV: `docs/p2p/artifacts/rf13_p2p_hypothesis_matrix.csv`
- Validador: `src/erp_fraud/storage/p2p_hypothesis_matrix.py`
- Script de verificación: `scripts/run_rf13_p2p_hypothesis_matrix.py`
- Evidencia por run: `run_results/<run_id>/rf13_p2p_hypothesis_matrix_validation.json`

## 3) Reglas de validación

Se valida:

1. headers obligatorios de CSV,
2. `process_step` permitido (`invoice_posting`, `goods_receipt`),
3. `test_id` existente en `tests/catalog`,
4. `fraud_type` consistente con el TestSpec,
5. `evidence_columns` dentro de `evidence_columns` del TestSpec,
6. `business_key_fields` dentro de keys mínimas de drilldown,
7. `source_deviation_id` con prefijo `P2P-`,
8. unicidad de `(hypothesis_id, test_id)`.

## 4) Ejecución manual

```bash
python3 scripts/run_rf13_p2p_hypothesis_matrix.py \
  --run-id rf13-p2p-matrix-check
```

Esperado:

- `status=OK` en JSON de salida.

