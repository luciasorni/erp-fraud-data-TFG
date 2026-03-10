from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.erp_fraud.catalog import (
    aggregate_findings_by_entity,
    compute_score_test,
    load_weights_config,
    resolve_ranking_top_k,
    resolve_test_weight,
    sort_ranking_rows_stable,
    write_ranking_outputs,
)


def test_resolve_test_weight_override_and_fallback() -> None:
    weights = {
        "defaults": {
            "severity_weights": {"low": 1.0, "high": 3.0},
            "fallback_weight": 0.5,
        },
        "overrides": {
            "by_test_id": {
                "TST-A": {"weight": 2.2},
            }
        },
    }
    assert resolve_test_weight(weights_config=weights, test_id="TST-A", severity="high") == pytest.approx(2.2)
    assert resolve_test_weight(weights_config=weights, test_id="TST-B", severity="high") == pytest.approx(3.0)
    assert resolve_test_weight(weights_config=weights, test_id="TST-B", severity="unknown") == pytest.approx(0.5)


def test_compute_score_test_formula() -> None:
    weights = {
        "defaults": {
            "severity_weights": {"low": 1.0, "medium": 2.0},
            "fallback_weight": 1.0,
        },
        "overrides": {
            "by_test_id": {
                "TST-X": {"weight": 4.0},
            }
        },
    }
    out = compute_score_test(
        weights_config=weights,
        test_id="TST-X",
        metrics={"duplicate_count": 3},
        severity="low",
    )
    assert out["weight"] == pytest.approx(4.0)
    assert out["metric_value"] == pytest.approx(3.0)
    assert out["score_test"] == pytest.approx(12.0)


def test_aggregate_findings_by_entity_is_deterministic() -> None:
    weights = {
        "defaults": {
            "severity_weights": {"low": 1.0, "medium": 2.0, "high": 3.0},
            "fallback_weight": 1.0,
        },
        "overrides": {"by_test_id": {}},
    }
    test_results = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "test_version": "1.0.0",
            "fraud_type": "duplicate_payment",
            "rows": [
                {
                    "entity_key": "belegnummer=B1|kreditor=V1|position=10",
                    "keys": {"belegnummer": "B1", "kreditor": "V1", "position": "10"},
                    "evidence_columns": ["betrag", "belegnummer"],
                    "metrics": {"duplicate_count": 2},
                    "severity": "high",
                },
                {
                    "entity_key": "belegnummer=B2|kreditor=V2|position=20",
                    "keys": {"belegnummer": "B2", "kreditor": "V2", "position": "20"},
                    "evidence_columns": ["betrag"],
                    "metrics": {"duplicate_count": 1},
                    "severity": "medium",
                },
            ],
        },
        {
            "test_id": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
            "test_version": "1.0.0",
            "fraud_type": "unusual_amount",
            "rows": [
                {
                    "entity_key": "belegnummer=B1|kreditor=V1|position=10",
                    "keys": {"belegnummer": "B1", "kreditor": "V1", "position": "10"},
                    "evidence_columns": ["z_score", "kreditor"],
                    "metrics": {"z_score": 4.0},
                    "severity": "medium",
                }
            ],
        },
    ]

    out1 = aggregate_findings_by_entity(test_results=test_results, weights_config=weights)
    out2 = aggregate_findings_by_entity(test_results=test_results, weights_config=weights)
    assert out1 == out2
    assert len(out1) == 2
    assert out1[0]["entity_key"] == "belegnummer=B1|kreditor=V1|position=10"
    assert out1[0]["score_total"] > out1[1]["score_total"]
    assert "TST-DUPLICATE-POSTINGS" in out1[0]["tests_triggered"]
    assert "TST-UNUSUAL-AMOUNT-BY-VENDOR" in out1[0]["tests_triggered"]


def test_sort_ranking_rows_stable_tie_breaker() -> None:
    rows = [
        {"entity_key": "kreditor=V2", "score_total": 10.0},
        {"entity_key": "kreditor=V1", "score_total": 10.0},
    ]
    sorted_rows = sort_ranking_rows_stable(rows)
    assert [row["entity_key"] for row in sorted_rows] == ["kreditor=V1", "kreditor=V2"]


def test_write_ranking_outputs_applies_top_k(tmp_path: Path) -> None:
    ranking_rows = [
        {"entity_key": "kreditor=V1", "score_total": 20.0},
        {"entity_key": "kreditor=V2", "score_total": 10.0},
        {"entity_key": "kreditor=V3", "score_total": 5.0},
    ]
    written = write_ranking_outputs(
        run_dir=tmp_path,
        ranking_rows=ranking_rows,
        formats=("json",),
        top_k=2,
    )
    json_path = Path(written["json"])
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["row_count"] == 2
    assert payload["top_k"] == 2
    assert [row["entity_key"] for row in payload["ranking"]] == ["kreditor=V1", "kreditor=V2"]


def test_load_weights_config_and_resolve_top_k_from_file() -> None:
    cfg = load_weights_config("config/weights.yaml")
    top_k = resolve_ranking_top_k(weights_config=cfg, default_top_k=99)
    assert top_k == 20
