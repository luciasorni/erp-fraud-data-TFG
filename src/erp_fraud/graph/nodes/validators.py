"""Validadores extraídos de legacy (fachada estable)."""

from __future__ import annotations

from typing import Any

from ...catalog import SCORE_SCHEMA_REQUIRED_FIELDS


def validate_hypotheses_output(output: Any, input_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(output, list) or not output:
        return {"passed": False, "errors": ["hypotheses debe ser lista no vacía"]}
    min_hypotheses = int(input_payload.get("min_hypotheses", 1) or 1)
    if min_hypotheses <= 0:
        min_hypotheses = 1
    min_distinct_fraud_types = int(input_payload.get("min_distinct_fraud_types", 1) or 1)
    if min_distinct_fraud_types <= 0:
        min_distinct_fraud_types = 1
    if len(output) < min_hypotheses:
        return {
            "passed": False,
            "errors": [f"hypotheses insuficientes: se requieren al menos {min_hypotheses}, recibidas {len(output)}"],
        }
    allowed_fraud_types = {
        str(value).strip()
        for value in input_payload.get("allowed_fraud_types", [])
        if str(value).strip()
    }
    allowed_process_steps = {
        str(value).strip()
        for value in input_payload.get("allowed_process_steps", [])
        if str(value).strip()
    }
    schema_columns_by_table_raw = input_payload.get("schema_columns_by_table", {})
    schema_columns_by_table: dict[str, set[str]] = {}
    if isinstance(schema_columns_by_table_raw, dict):
        for table, columns in schema_columns_by_table_raw.items():
            table_name = str(table).strip()
            if not table_name:
                continue
            if isinstance(columns, list):
                schema_columns_by_table[table_name] = {
                    str(col).strip() for col in columns if str(col).strip()
                }

    errors: list[str] = []
    fraud_types_observed: set[str] = set()
    for idx, item in enumerate(output):
        if not isinstance(item, dict):
            errors.append(f"hypotheses[{idx}] debe ser objeto")
            continue
        hypothesis_id = str(item.get("hypothesis_id", "")).strip()
        title = str(item.get("title", "")).strip()
        if not hypothesis_id:
            errors.append(f"hypotheses[{idx}].hypothesis_id vacío")
        if not title:
            errors.append(f"hypotheses[{idx}].title vacío")
        fraud_type = str(item.get("fraud_type", "")).strip()
        process_step = str(item.get("process_step", "")).strip()
        if not fraud_type:
            errors.append(f"hypotheses[{idx}].fraud_type vacío")
        elif allowed_fraud_types and fraud_type not in allowed_fraud_types:
            errors.append(f"hypotheses[{idx}].fraud_type fuera de catálogo: {fraud_type}")
        else:
            fraud_types_observed.add(fraud_type)
        if not process_step:
            errors.append(f"hypotheses[{idx}].process_step vacío")
        elif allowed_process_steps and process_step not in allowed_process_steps:
            errors.append(f"hypotheses[{idx}].process_step fuera de catálogo: {process_step}")
        evidence_requirements = item.get("evidence_requirements", [])
        if not isinstance(evidence_requirements, list):
            errors.append(f"hypotheses[{idx}].evidence_requirements debe ser lista")
            evidence_requirements = []
        for req_idx, req in enumerate(evidence_requirements):
            if not isinstance(req, dict):
                errors.append(f"hypotheses[{idx}].evidence_requirements[{req_idx}] debe ser objeto")
                continue
            table = str(req.get("table", "")).strip()
            column = str(req.get("column", "")).strip()
            if not table or not column:
                errors.append(
                    f"hypotheses[{idx}].evidence_requirements[{req_idx}] requiere table/column no vacíos"
                )
                continue
            if schema_columns_by_table:
                table_cols = schema_columns_by_table.get(table)
                if table_cols is None:
                    errors.append(f"hypotheses[{idx}] evidencia usa tabla no existente: {table}")
                    continue
                if column not in table_cols:
                    errors.append(
                        f"hypotheses[{idx}] evidencia usa columna no existente: {table}.{column}"
                    )
        sources = item.get("sources", [])
        if not isinstance(sources, list) or not sources:
            errors.append(f"hypotheses[{idx}].sources debe ser lista no vacía")
            continue
        source_types = {
            str(source.get("type", "")).strip()
            for source in sources
            if isinstance(source, dict)
        }
        if "test_catalog" not in source_types:
            errors.append(f"hypotheses[{idx}].sources sin test_catalog")
        if "schema_summary" not in source_types:
            errors.append(f"hypotheses[{idx}].sources sin schema_summary")
    if len(fraud_types_observed) < min_distinct_fraud_types:
        errors.append(
            "diversidad insuficiente de fraud_type: "
            f"se requieren {min_distinct_fraud_types}, observados {len(fraud_types_observed)}"
        )
    return {"passed": len(errors) == 0, "errors": errors}


def validate_selected_tests_output(output: Any, input_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(output, list):
        return {"passed": False, "errors": ["selected_tests debe ser lista"]}
    allowlist = input_payload.get("allowlist_ids", [])
    allowlist_set = {str(item).strip() for item in allowlist if str(item).strip()}
    errors: list[str] = []
    for idx, row in enumerate(output):
        if not isinstance(row, dict):
            errors.append(f"selected_tests[{idx}] debe ser objeto")
            continue
        hypothesis_id = str(row.get("hypothesis_id", "")).strip()
        test_id = str(row.get("test_id", "")).strip()
        if not hypothesis_id:
            errors.append(f"selected_tests[{idx}].hypothesis_id vacío")
        if not test_id:
            errors.append(f"selected_tests[{idx}].test_id vacío")
        elif allowlist_set and test_id not in allowlist_set:
            errors.append(f"selected_tests[{idx}].test_id fuera de allowlist: {test_id}")
    return {"passed": len(errors) == 0, "errors": errors}


def validate_explanations_output(output: Any, input_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(output, list) or not output:
        return {"passed": False, "errors": ["explanations debe ser lista no vacía"]}
    findings = input_payload.get("findings", [])
    catalog_ids_raw = input_payload.get("catalog_test_ids", [])
    schema_columns_raw = input_payload.get("schema_columns", [])
    catalog_test_ids = (
        {str(item).strip() for item in catalog_ids_raw if str(item).strip()}
        if isinstance(catalog_ids_raw, list)
        else set()
    )
    schema_columns = (
        {str(item).strip() for item in schema_columns_raw if str(item).strip()}
        if isinstance(schema_columns_raw, list)
        else set()
    )
    try:
        from .explainer import _validate_explanations_guardrails

        _validate_explanations_guardrails(
            explanations=[item for item in output if isinstance(item, dict)],
            findings=[item for item in findings if isinstance(item, dict)],
            catalog_test_ids=catalog_test_ids,
            schema_columns=schema_columns,
        )
    except Exception as exc:
        return {"passed": False, "errors": [str(exc)]}
    return {"passed": True, "errors": []}


def validate_scores_output(output: Any, input_payload: dict[str, Any]) -> dict[str, Any]:
    _ = input_payload
    if not isinstance(output, list) or not output:
        return {"passed": False, "errors": ["scores debe ser lista no vacía"]}
    first = output[0]
    if not isinstance(first, dict):
        return {"passed": False, "errors": ["scores[0] debe ser objeto"]}
    missing_schema_fields = [field for field in SCORE_SCHEMA_REQUIRED_FIELDS if field not in first]
    if missing_schema_fields:
        return {
            "passed": False,
            "errors": [f"scores[0] no cumple ScoreSchema, faltan: {missing_schema_fields}"],
        }
    ranking = first.get("ranking", [])
    if not isinstance(ranking, list):
        return {"passed": False, "errors": ["scores[0].ranking debe ser lista"]}
    for idx, row in enumerate(ranking):
        if not isinstance(row, dict):
            return {"passed": False, "errors": [f"ranking[{idx}] debe ser objeto"]}
        if not str(row.get("entity_key", "")).strip():
            return {"passed": False, "errors": [f"ranking[{idx}].entity_key vacío"]}
    fraud_type_probs = first.get("fraud_type_probs", [])
    if fraud_type_probs:
        if not isinstance(fraud_type_probs, list):
            return {"passed": False, "errors": ["scores[0].fraud_type_probs debe ser lista"]}
        for idx, row in enumerate(fraud_type_probs):
            if not isinstance(row, dict):
                return {"passed": False, "errors": [f"fraud_type_probs[{idx}] debe ser objeto"]}
            if not str(row.get("fraud_type", "")).strip():
                return {"passed": False, "errors": [f"fraud_type_probs[{idx}].fraud_type vacío"]}
            prob = float(row.get("probability", 0.0) or 0.0)
            if prob < 0.0 or prob > 1.0:
                return {
                    "passed": False,
                    "errors": [f"fraud_type_probs[{idx}].probability fuera de [0,1]: {prob}"],
                }
    return {"passed": True, "errors": []}
