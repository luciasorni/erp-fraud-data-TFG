"""Agregación y ranking base de hallazgos (RF07-03)."""

from __future__ import annotations

from typing import Any

from .scoring import compute_score_test


def _merge_evidence_columns(current: list[str], incoming: Any) -> list[str]:
    if not isinstance(incoming, list):
        return current
    merged = set(current)
    for column in incoming:
        if isinstance(column, str) and column.strip():
            merged.add(column.strip())
    return sorted(merged)


def aggregate_findings_by_entity(
    *,
    test_results: list[dict[str, Any]],
    weights_config: dict[str, Any],
) -> list[dict[str, Any]]:
    """Agrega hallazgos por entity_key sumando score_test y recopilando contexto."""
    aggregated: dict[str, dict[str, Any]] = {}

    for test_result in test_results:
        test_id = str(test_result.get("test_id", "")).strip()
        test_version = str(test_result.get("test_version", "")).strip()
        fraud_type = str(test_result.get("fraud_type", "")).strip()
        rows = test_result.get("rows")
        if not test_id or not isinstance(rows, list):
            continue

        for row in rows:
            if not isinstance(row, dict):
                continue
            entity_key = str(row.get("entity_key", "")).strip()
            if not entity_key:
                continue

            keys = row.get("keys") if isinstance(row.get("keys"), dict) else {}
            evidence_columns = row.get("evidence_columns")
            metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
            severity = row.get("severity")
            severity_value = str(severity).strip() if severity is not None else None

            score_parts = compute_score_test(
                weights_config=weights_config,
                test_id=test_id,
                metrics=metrics,
                severity=severity_value or None,
            )

            if entity_key not in aggregated:
                aggregated[entity_key] = {
                    "entity_key": entity_key,
                    "keys": dict(keys),
                    "score_total": 0.0,
                    "findings_count": 0,
                    "tests_triggered": [],
                    "fraud_types": [],
                    "evidence_columns": [],
                    "score_breakdown": [],
                }

            current = aggregated[entity_key]
            current["score_total"] = float(current["score_total"]) + float(score_parts["score_test"])
            current["findings_count"] = int(current["findings_count"]) + 1
            current["evidence_columns"] = _merge_evidence_columns(
                current["evidence_columns"],
                evidence_columns,
            )

            if test_id and test_id not in current["tests_triggered"]:
                current["tests_triggered"].append(test_id)
            if fraud_type and fraud_type not in current["fraud_types"]:
                current["fraud_types"].append(fraud_type)

            current["score_breakdown"].append(
                {
                    "test_id": test_id,
                    "test_version": test_version,
                    "weight": float(score_parts["weight"]),
                    "metric_value": float(score_parts["metric_value"]),
                    "score_test": float(score_parts["score_test"]),
                }
            )

    ranked = list(aggregated.values())
    for row in ranked:
        row["tests_triggered"] = sorted(row["tests_triggered"])
        row["fraud_types"] = sorted(row["fraud_types"])
        row["score_breakdown"] = sorted(
            row["score_breakdown"],
            key=lambda item: (
                str(item.get("test_id", "")),
                str(item.get("test_version", "")),
                float(item.get("score_test", 0.0)),
            ),
        )

    ranked.sort(key=lambda row: (-float(row["score_total"]), str(row["entity_key"])))
    return ranked
