"""Helpers de findings/ranking/explanations extraídos de legacy (fachada estable)."""

from __future__ import annotations

from typing import Any

from . import deps
from .persist_utils import normalize_columns
from ...catalog import RESULT_SCHEMA_VERSION, get_result_schema_required_fields


def build_hypotheses_from_tools(**kwargs: Any) -> list[dict[str, Any]]:
    catalog_out = kwargs.get("catalog_out", {})
    schema_out = kwargs.get("schema_out", {})
    data_catalog_out = kwargs.get("data_catalog_out", {})
    kb_status = str(kwargs.get("kb_status", "")).strip()
    kb_query = str(kwargs.get("kb_query", "")).strip()
    kb_top_k = int(kwargs.get("kb_top_k", 3) or 3)
    kb_hits = kwargs.get("kb_hits", [])
    max_hypotheses = int(kwargs.get("max_hypotheses", 1) or 1)

    catalog_tests = catalog_out.get("tests", []) if isinstance(catalog_out, dict) else []
    if not isinstance(catalog_tests, list):
        catalog_tests = []

    tests_by_fraud_type: dict[str, list[str]] = {}
    tests_by_process_step: dict[str, list[str]] = {}
    for row in catalog_tests:
        if not isinstance(row, dict):
            continue
        test_id = str(row.get("id", "")).strip()
        if not test_id:
            continue
        fraud_type = str(row.get("fraud_type", "")).strip() or "unknown"
        process_step = str(row.get("process_step", "")).strip() or "unknown_step"
        tests_by_fraud_type.setdefault(fraud_type, []).append(test_id)
        tests_by_process_step.setdefault(process_step, []).append(test_id)

    table_names: list[str] = []
    schema_payload = schema_out.get("payload", {}) if isinstance(schema_out, dict) else {}
    schema_columns_by_table: dict[str, list[str]] = {}
    if isinstance(schema_payload, dict):
        names = schema_payload.get("table_names", [])
        if isinstance(names, list):
            table_names = [str(item).strip() for item in names if str(item).strip()]
        raw_cols = schema_payload.get("columns_by_table", {})
        if isinstance(raw_cols, dict):
            schema_columns_by_table = {
                str(table).strip(): [str(col).strip() for col in cols if str(col).strip()]
                for table, cols in raw_cols.items()
                if str(table).strip() and isinstance(cols, list)
            }

    data_payload = data_catalog_out.get("payload", {}) if isinstance(data_catalog_out, dict) else {}
    data_entries = data_payload.get("entries", []) if isinstance(data_payload, dict) else []
    if not isinstance(data_entries, list):
        data_entries = []
    data_evidence_raw = [
        {"table": str(row.get("table", "")).strip(), "column": str(row.get("column", "")).strip()}
        for row in data_entries[:6]
        if isinstance(row, dict)
    ]
    data_evidence_raw = [row for row in data_evidence_raw if row["table"] and row["column"]]
    data_evidence = [
        row
        for row in data_evidence_raw
        if row["table"] in schema_columns_by_table and row["column"] in set(schema_columns_by_table[row["table"]])
    ]
    if not data_evidence:
        for table_name in table_names[:2]:
            for col_name in schema_columns_by_table.get(table_name, [])[:3]:
                data_evidence.append({"table": table_name, "column": col_name})

    kb_chunks = [
        str(hit.get("chunk_id", "")).strip()
        for hit in kb_hits
        if isinstance(hit, dict) and str(hit.get("chunk_id", "")).strip()
    ]

    if not tests_by_fraud_type:
        return [
            {
                "hypothesis_id": "HYP-001",
                "title": "Insufficient catalog context to derive fraud hypothesis",
                "description": "No hay tests disponibles en el catálogo para crear hipótesis específicas.",
                "fraud_type": "unknown",
                "process_step": "unknown_step",
                "evidence_requirements": [],
                "candidate_test_ids": [],
                "sources": [
                    {"type": "test_catalog", "catalog_tests_count": int(catalog_out.get("count", 0) or 0)},
                    {"type": "schema_summary", "table_names": table_names},
                    {"type": "data_catalog", "field_count": int(data_payload.get("count", 0) or 0)},
                ],
                "source": "alpha_loop_context",
                "tool_context": {
                    "catalog_tests_count": int(catalog_out.get("count", 0) or 0),
                    "schema_tables_count": int(schema_payload.get("count", 0) or 0),
                    "kb_search_status": kb_status,
                    "kb_hits_count": len(kb_chunks),
                    "data_catalog_fields_count": int(data_payload.get("count", 0) or 0),
                },
            }
        ]

    hypotheses: list[dict[str, Any]] = []
    for idx, fraud_type in enumerate(sorted(tests_by_fraud_type.keys())[:max_hypotheses], start=1):
        candidate_ids = sorted(tests_by_fraud_type[fraud_type])[:3]
        process_step = "unknown_step"
        for step, step_test_ids in tests_by_process_step.items():
            overlap = sorted(set(step_test_ids).intersection(set(candidate_ids)))
            if overlap:
                process_step = step
                break
        title = f"Hypothesis for {fraud_type.replace('_', ' ').title()} patterns"
        description = (
            f"Comprobar señales asociadas a '{fraud_type}' usando tests del catálogo y contexto de datos disponible."
        )
        sources: list[dict[str, Any]] = [
            {
                "type": "test_catalog",
                "fraud_type": fraud_type,
                "test_ids": candidate_ids,
                "catalog_tests_count": int(catalog_out.get("count", 0) or 0),
            },
            {
                "type": "schema_summary",
                "table_names": table_names,
                "table_count": int(schema_payload.get("count", 0) or 0),
            },
            {
                "type": "data_catalog",
                "fields": data_evidence,
                "field_count": int(data_payload.get("count", 0) or 0),
            },
        ]
        if kb_status == "OK":
            sources.append(
                {
                    "type": "kb_search",
                    "query": kb_query,
                    "top_k": int(kb_top_k),
                    "chunk_ids": kb_chunks[:kb_top_k],
                    "hits_count": len(kb_chunks),
                }
            )

        evidence_requirements = [
            {"table": row["table"], "column": row["column"]}
            for row in data_evidence[:3]
            if row.get("table") and row.get("column")
        ]

        hypotheses.append(
            {
                "hypothesis_id": f"HYP-{idx:03d}",
                "title": title,
                "description": description,
                "fraud_type": fraud_type,
                "process_step": process_step,
                "evidence_requirements": evidence_requirements,
                "candidate_test_ids": candidate_ids,
                "sources": sources,
                "source": "alpha_loop_context",
                "tool_context": {
                    "catalog_tests_count": int(catalog_out.get("count", 0) or 0),
                    "schema_tables_count": int(schema_payload.get("count", 0) or 0),
                    "kb_search_status": kb_status,
                    "kb_hits_count": len(kb_chunks),
                    "data_catalog_fields_count": int(data_payload.get("count", 0) or 0),
                },
            }
        )
    return hypotheses


def score_test_against_hypothesis(*, hypothesis_text: str, test_spec: dict[str, Any]) -> tuple[int, list[str]]:
    text = hypothesis_text.lower()
    test_id = str(test_spec.get("id", "")).strip()
    fraud_type = str(test_spec.get("fraud_type", "")).strip().lower()
    test_name = str(test_spec.get("name", "")).strip().lower()
    tags = [str(tag).strip().lower() for tag in test_spec.get("tags", []) if str(tag).strip()]
    score = 0
    reasons: list[str] = []
    keyword_rules: list[tuple[str, str]] = [
        ("split", "split"),
        ("threshold", "threshold"),
        ("just below", "threshold"),
        ("duplicate", "duplicate"),
        ("round", "round"),
        ("sequence", "sequence"),
        ("negative", "inventory"),
        ("material", "material"),
        ("amount", "amount"),
    ]
    for key, token in keyword_rules:
        if key in text and (token in test_id.lower() or token in test_name or token in ",".join(tags) or token in fraud_type):
            score += 2
            reasons.append(f"keyword:{key}->{token}")
    fraud_type_aliases: list[tuple[str, str]] = [
        ("authorization", "authorization_bypass"),
        ("duplicate", "duplicate_payment"),
        ("anomaly", "amount_anomaly"),
        ("inventory", "inventory_anomaly"),
        ("pattern", "suspicious_payment_pattern"),
    ]
    for key, expected in fraud_type_aliases:
        if key in text and fraud_type == expected:
            score += 4
            reasons.append(f"fraud_type:{expected}")
    if test_id and test_id.lower() in text:
        score += 5
        reasons.append("explicit_test_id")
    return score, reasons


def build_schema_columns_lookup(schema_payload: dict[str, Any]) -> dict[str, set[str]]:
    lookup: dict[str, set[str]] = {}
    tables = schema_payload.get("tables", []) if isinstance(schema_payload.get("tables"), list) else []
    for table in tables:
        if not isinstance(table, dict):
            continue
        table_name = str(table.get("table_name", "")).strip()
        if not table_name:
            continue
        cols_raw = table.get("columns", [])
        if not isinstance(cols_raw, list):
            continue
        col_names = {
            str(col.get("name", col.get("column_name", ""))).strip()
            for col in cols_raw
            if isinstance(col, dict) and str(col.get("name", col.get("column_name", ""))).strip()
        }
        lookup[table_name] = col_names
    return lookup


def test_spec_is_schema_compatible(
    *,
    test_spec: dict[str, Any],
    schema_columns_lookup: dict[str, set[str]],
) -> tuple[bool, str]:
    requirements = test_spec.get("table_requirements", [])
    if not isinstance(requirements, list) or not requirements:
        return True, ""
    test_id = str(test_spec.get("id", "")).strip() or "<unknown_test>"
    for req in requirements:
        if not isinstance(req, dict):
            continue
        table_name = str(req.get("table", "")).strip()
        required_columns = req.get("required_columns", [])
        if not table_name:
            continue
        if table_name not in schema_columns_lookup:
            return False, f"{test_id}: tabla requerida no disponible en schema_summary: {table_name}"
        if not isinstance(required_columns, list):
            continue
        missing_columns = [
            str(col).strip()
            for col in required_columns
            if str(col).strip() and str(col).strip() not in schema_columns_lookup[table_name]
        ]
        if missing_columns:
            return False, f"{test_id}: columnas requeridas no disponibles en {table_name}: {missing_columns}"
    return True, ""


def normalize_result_schema_payload(result: dict[str, Any]) -> dict[str, Any]:
    row = dict(result)
    required_fields = get_result_schema_required_fields()
    defaults: dict[str, Any] = {
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "generated_at_utc": "",
        "test_id": "",
        "test_version": "",
        "fraud_type": "",
        "status": "UNKNOWN",
        "finding_count": 0,
        "duration_ms": int(row.get("runner_duration_ms", 0) or row.get("duration_ms", 0) or 0),
        "columns": [],
        "rows": [],
        "metadata": {},
    }
    for field in required_fields:
        if field not in row or row.get(field) is None:
            row[field] = defaults.get(field)
    row["result_schema_version"] = str(row.get("result_schema_version") or RESULT_SCHEMA_VERSION)
    row["test_id"] = str(row.get("test_id", "")).strip()
    row["test_version"] = str(row.get("test_version", "")).strip()
    row["fraud_type"] = str(row.get("fraud_type", "")).strip()
    row["status"] = str(row.get("status", "UNKNOWN")).strip().upper() or "UNKNOWN"
    row["finding_count"] = int(row.get("finding_count", 0) or 0)
    row["duration_ms"] = int(row.get("duration_ms", 0) or 0)
    if not isinstance(row.get("columns"), list):
        row["columns"] = []
    if not isinstance(row.get("rows"), list):
        row["rows"] = []
    if not isinstance(row.get("metadata"), dict):
        row["metadata"] = {}
    return row


def to_test_run_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "test_id": str(result.get("test_id", "")).strip(),
        "version": str(result.get("test_version", "")).strip(),
        "status": str(result.get("status", "UNKNOWN")).strip().upper(),
        "duration_ms": int(result.get("runner_duration_ms", result.get("duration_ms", 0)) or 0),
        "error_summary": str(result.get("error_summary", "")).strip(),
        "finding_count": int(result.get("finding_count", 0) or 0),
    }


def build_explanation_from_finding(result: dict[str, Any], *, entity_key: str = "") -> dict[str, Any]:
    test_id = str(result.get("test_id", "")).strip()
    finding_count = int(result.get("finding_count", 0) or 0)
    status = str(result.get("status", "UNKNOWN")).strip().upper()
    fraud_type = str(result.get("fraud_type", "")).strip()
    columns = normalize_columns(result.get("columns", []))
    rows = result.get("rows", [])
    first_entity_key = ""
    first_keys: dict[str, Any] = {}
    first_evidence_columns: list[str] = []
    selected_row: dict[str, Any] = {}
    if isinstance(rows, list):
        if entity_key:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                row_entity_key = str(row.get("entity_key", "")).strip()
                if row_entity_key == entity_key:
                    selected_row = row
                    break
        if not selected_row and rows and isinstance(rows[0], dict):
            selected_row = rows[0]
    if selected_row:
        first_entity_key = str(selected_row.get("entity_key", "")).strip()
        maybe_keys = selected_row.get("keys")
        if isinstance(maybe_keys, dict):
            first_keys = {str(k): str(v) for k, v in maybe_keys.items() if str(k).strip()}
        maybe_evidence = selected_row.get("evidence_columns")
        if isinstance(maybe_evidence, list):
            first_evidence_columns = normalize_columns(maybe_evidence)
    if status in {"ERROR", "TIMEOUT"}:
        summary = f"{test_id} terminó en {status}; revisar error_summary y logs del runner."
    elif finding_count <= 0:
        summary = f"{test_id} no activó hallazgos en este run."
    else:
        summary = (
            f"{test_id} activó {finding_count} hallazgos para fraud_type={fraud_type or 'unknown'} "
            f"usando evidencia en columnas del resultado."
        )
    return {
        "test_id": test_id,
        "cited_test_id": test_id,
        "status": status,
        "fraud_type": fraud_type,
        "finding_count": finding_count,
        "referenced_columns": columns[:8],
        "cited_keys": first_keys,
        "cited_evidence_columns": first_evidence_columns,
        "sample_entity_key": first_entity_key,
        "summary": summary,
        "source": "explainer_stub_guarded",
    }


def build_explanations_for_ranked_entities(
    *,
    findings: list[dict[str, Any]],
    ranking: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    if top_k <= 0:
        return []
    top_entities: list[str] = []
    for row in ranking[:top_k]:
        if not isinstance(row, dict):
            continue
        entity_key = str(row.get("entity_key", "")).strip()
        if entity_key:
            top_entities.append(entity_key)
    if not top_entities:
        return []
    explanations: list[dict[str, Any]] = []
    for entity_key in top_entities:
        matched = False
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            rows = finding.get("rows", [])
            if not isinstance(rows, list):
                continue
            if not any(isinstance(row, dict) and str(row.get("entity_key", "")).strip() == entity_key for row in rows):
                continue
            item = build_explanation_from_finding(finding, entity_key=entity_key)
            item["summary"] = (
                f"{item['test_id']} respalda hallazgo para entity_key={entity_key} "
                f"con evidencia citada del resultado."
            )
            explanations.append(item)
            matched = True
            break
        if not matched:
            continue
    return explanations


def sanitize_explanations_against_findings(
    *,
    explanations: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings_by_test: dict[str, dict[str, Any]] = {}
    for row in findings:
        if not isinstance(row, dict):
            continue
        test_id = str(row.get("test_id", "")).strip()
        if test_id:
            findings_by_test[test_id] = row
    sanitized: list[dict[str, Any]] = []
    for item in explanations:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        test_id = str(row.get("test_id", "")).strip()
        if not test_id or test_id not in findings_by_test:
            continue
        finding = findings_by_test[test_id]
        row["cited_test_id"] = test_id
        allowed_columns = set(normalize_columns(finding.get("columns", [])))
        row["referenced_columns"] = [col for col in normalize_columns(row.get("referenced_columns", [])) if col in allowed_columns]
        finding_rows = finding.get("rows", [])
        first_row = finding_rows[0] if isinstance(finding_rows, list) and finding_rows else {}
        allowed_keys = first_row.get("keys", {}) if isinstance(first_row, dict) else {}
        if not isinstance(allowed_keys, dict):
            allowed_keys = {}
        cited_keys = row.get("cited_keys", {})
        if not isinstance(cited_keys, dict):
            cited_keys = {}
        row["cited_keys"] = {str(k): str(v) for k, v in cited_keys.items() if str(k).strip() and str(k) in allowed_keys}
        allowed_evidence = []
        maybe_evidence = first_row.get("evidence_columns", []) if isinstance(first_row, dict) else []
        if isinstance(maybe_evidence, list):
            allowed_evidence = normalize_columns(maybe_evidence)
        row["cited_evidence_columns"] = [
            col for col in normalize_columns(row.get("cited_evidence_columns", [])) if col in set(allowed_evidence)
        ]
        sanitized.append(row)
    return sanitized


def build_structured_explainer_feedback(errors: list[str]) -> list[dict[str, Any]]:
    structured: list[dict[str, Any]] = []
    for raw in errors:
        err = str(raw).strip()
        if not err:
            continue
        code = "UNKNOWN"
        if "no ejecutado" in err or "fuera de catálogo" in err:
            code = "TEST_ID_INVALID"
        elif "columnas no presentes" in err:
            code = "REFERENCED_COLUMNS_INVALID"
        elif "keys inexistentes" in err or "fuera de schema_summary" in err:
            code = "CITED_KEYS_INVALID"
        elif "evidence_columns no presentes" in err:
            code = "EVIDENCE_COLUMNS_INVALID"
        structured.append({"code": code, "message": err})
    return structured


def build_acfe_reference_via_kb(
    *,
    kb_enabled: bool,
    kb_query: str,
    kb_top_k: int,
    kb_chroma_config_path: str,
    base_dir: str,
) -> dict[str, Any]:
    if not kb_enabled:
        return {"status": "SKIPPED", "query": kb_query, "hits": []}
    try:
        tool = deps.KBSearchTool(
            kb_chroma_config_path=kb_chroma_config_path,
            base_dir=base_dir,
        )
        result = tool.search(query=kb_query, top_k=kb_top_k)
        hits = result.get("hits", []) if isinstance(result, dict) else []
        out_hits: list[dict[str, Any]] = []
        for row in hits[:kb_top_k]:
            if not isinstance(row, dict):
                continue
            metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
            out_hits.append(
                {
                    "chunk_id": str(row.get("chunk_id", "")).strip(),
                    "score": float(row.get("score", 0.0) or 0.0),
                    "source_path": str(metadata.get("source_path", "")).strip(),
                    "source_id": str(metadata.get("source_id", "")).strip(),
                }
            )
        return {"status": "OK", "query": kb_query, "hits": out_hits}
    except Exception as exc:
        return {
            "status": f"ERROR:{type(exc).__name__}",
            "query": kb_query,
            "hits": [],
            "error": str(exc),
        }
