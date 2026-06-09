from __future__ import annotations

import json
from pathlib import Path

import duckdb

from src.erp_fraud.graph import run_graph_full
from src.erp_fraud.graph.nodes import second_level_explainer as second_level_module


def test_rf16_second_level_agent_runs_after_persist(tmp_path: Path) -> None:
    db_path = tmp_path / "rf16_node.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE fraud_1 (
                Kreditor VARCHAR,
                Belegnummer VARCHAR,
                Position VARCHAR,
                Betrag DOUBLE
            )
            """
        )
        conn.executemany(
            "INSERT INTO fraud_1 VALUES (?, ?, ?, ?)",
            [
                ("V1", "D1", "10", 8039295.0),
                ("V1", "D1", "20", 4984.0),
                ("V2", "D2", "10", 120.0),
            ],
        )
    finally:
        conn.close()

    out = run_graph_full(
        run_id="rf16-node-it",
        dataset_hash="hash-rf16-node",
        input_zip="fixture.zip",
        run_metadata_overrides={
            "db_path": str(db_path),
            "schema_name": "main",
            "table_name": "fraud_1",
            "catalog_path": "tests/catalog",
            "persist_base_dir": str(tmp_path / "run_results"),
            "llm_mode": "stub",
            "kb_index_enabled": False,
            "kb_search_enabled": False,
            "rf16_include_current_run": True,
            "rf16_auto_latest_p2p_o2c": False,
            "rf16_compare_run_ids": [],
        },
    )

    node_status = out.run_metadata.get("node_status", {})
    assert isinstance(node_status, dict)
    assert node_status.get("persist") == "OK"
    assert node_status.get("second_level_explainer") == "OK"

    graph_dir = Path(str(out.run_metadata.get("persist_graph_dir", "")).strip())
    assert (graph_dir / "second_level_analysis.json").exists()
    assert (graph_dir / "second_level_analysis.md").exists()

    payload = json.loads((graph_dir / "second_level_analysis.json").read_text(encoding="utf-8"))
    assert payload.get("rf_task") == "RF16"
    assert isinstance(payload.get("deterministic_comparison"), dict)
    assert isinstance(payload.get("llm_insights"), dict)
    recommendation_items = payload["llm_insights"]["normalized"]["recommendation_items"]
    assert any(row.get("status") == "audit_procedure" for row in recommendation_items)
    recommended_test_items = [row for row in recommendation_items if row.get("status") == "recommended_test"]
    assert recommended_test_items
    selected_test_ids = set(payload["deterministic_comparison"]["runs"][0]["selected_test_ids"])
    recommended_test_ids = {row["attributes"]["test_id"] for row in recommended_test_items}
    assert recommended_test_ids.isdisjoint(selected_test_ids)
    assert payload["llm_insights"]["recommended_tests_filtered_out"]
    assert payload["llm_insights"]["recommended_tests_candidate_count"] > 0
    assert payload["llm_insights"]["recommended_tests_fallback_used"] is True
    runtime = out.run_metadata["llm_runtime_by_node"]["second_level_explainer"]
    assert runtime["status"] == "SKIPPED"
    assert runtime["fallback_used"] is True
    assert runtime["skip_reason"] == "llm_mode_stub"
    assert runtime["mode_effective"] == "stub"
    assert runtime["provider"] == "openai"
    assert runtime["models_config_source"] == "config"


def test_rf16_second_level_agent_degrades_when_alpha_loop_runtime_error(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "rf16_node_degraded.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE fraud_1 (
                Kreditor VARCHAR,
                Belegnummer VARCHAR,
                Position VARCHAR,
                Betrag DOUBLE
            )
            """
        )
        conn.executemany(
            "INSERT INTO fraud_1 VALUES (?, ?, ?, ?)",
            [
                ("V1", "D1", "10", 8039295.0),
                ("V1", "D1", "20", 4984.0),
                ("V2", "D2", "10", 120.0),
            ],
        )
    finally:
        conn.close()

    def _raise_runtime_error(**_kwargs):
        raise RuntimeError("alpha_loop second_level_explainer terminó en estado=ERROR")

    monkeypatch.setattr(second_level_module, "_run_alpha_loop_for_node", _raise_runtime_error)

    out = run_graph_full(
        run_id="rf16-node-degraded-it",
        dataset_hash="hash-rf16-node-degraded",
        input_zip="fixture.zip",
        run_metadata_overrides={
            "db_path": str(db_path),
            "schema_name": "main",
            "table_name": "fraud_1",
            "catalog_path": "tests/catalog",
            "persist_base_dir": str(tmp_path / "run_results"),
            "llm_mode": "stub",
            "kb_index_enabled": False,
            "kb_search_enabled": False,
            "rf16_include_current_run": True,
            "rf16_auto_latest_p2p_o2c": False,
            "rf16_compare_run_ids": [],
        },
    )

    node_status = out.run_metadata.get("node_status", {})
    assert node_status.get("second_level_explainer") == "OK"
    assert out.run_metadata["second_level_explainer_status"] == "OK_WITH_WARNINGS"
    assert out.run_metadata["second_level_explainer_degraded"] is True
    runtime = out.run_metadata["llm_runtime_by_node"]["second_level_explainer"]
    assert runtime["status"] == "DEGRADED"
    assert runtime["fallback_used"] is True

    graph_dir = Path(str(out.run_metadata.get("persist_graph_dir", "")).strip())
    payload = json.loads((graph_dir / "second_level_analysis.json").read_text(encoding="utf-8"))
    assert payload["rf_task"] == "RF16"
    assert isinstance(payload["llm_insights"]["normalized"]["recommendation_items"], list)


def test_rf16_second_level_agent_degrades_when_compare_run_artifacts_are_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "rf16_node_missing_context.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE fraud_1 (
                Kreditor VARCHAR,
                Belegnummer VARCHAR,
                Position VARCHAR,
                Betrag DOUBLE
            )
            """
        )
        conn.executemany(
            "INSERT INTO fraud_1 VALUES (?, ?, ?, ?)",
            [
                ("V1", "D1", "10", 8039295.0),
                ("V1", "D1", "20", 4984.0),
                ("V2", "D2", "10", 120.0),
            ],
        )
    finally:
        conn.close()

    out = run_graph_full(
        run_id="rf16-node-missing-context-it",
        dataset_hash="hash-rf16-node-missing-context",
        input_zip="fixture.zip",
        run_metadata_overrides={
            "db_path": str(db_path),
            "schema_name": "main",
            "table_name": "fraud_1",
            "catalog_path": "tests/catalog",
            "persist_base_dir": str(tmp_path / "run_results"),
            "llm_mode": "stub",
            "kb_index_enabled": False,
            "kb_search_enabled": False,
            "rf16_include_current_run": False,
            "rf16_auto_latest_p2p_o2c": False,
            "rf16_compare_run_ids": ["missing-run"],
        },
    )

    node_status = out.run_metadata.get("node_status", {})
    assert node_status.get("second_level_explainer") == "OK"
    assert out.run_metadata["second_level_comparison_status"] == "INSUFFICIENT_CONTEXT"
    assert out.run_metadata["second_level_explainer_status"] == "OK_WITH_WARNINGS"

    graph_dir = Path(str(out.run_metadata.get("persist_graph_dir", "")).strip())
    payload = json.loads((graph_dir / "second_level_analysis.json").read_text(encoding="utf-8"))
    assert payload["deterministic_comparison"]["comparison_status"] == "INSUFFICIENT_CONTEXT"
    assert payload["llm_insights"]["normalized"]["comparison_items"][0]["status"] == "insufficient_context"


def test_rf16_filters_executed_recommended_tests_mixed_shapes() -> None:
    filtered, removed = second_level_module._filter_recommended_tests_against_executed(
        recommended_tests=[
            "TST-ALREADY-RUN",
            {"test_id": "TST-KEEP", "rationale": "Cobertura adicional"},
            {"test_id": "TST-UNKNOWN", "rationale": "No existe en candidatos"},
            {"id": "TST-ALREADY-ID"},
            {"name": "TST-ALREADY-NAME"},
            {"title": "TST-ALREADY-TITLE"},
            {"test_id": "TST-ALREADY-RUN", "rationale": "Duplicado"},
        ],
        executed_test_ids=[
            "TST-ALREADY-RUN",
            "TST-ALREADY-ID",
            "TST-ALREADY-NAME",
            "TST-ALREADY-TITLE",
        ],
        available_tests_not_executed=[
            {"test_id": "TST-KEEP", "rationale": "Cobertura adicional"},
            {"test_id": "TST-OTHER", "rationale": "Otro candidato"},
        ],
    )

    assert filtered == [{"test_id": "TST-KEEP", "rationale": "Cobertura adicional"}]
    assert removed == [
        "TST-ALREADY-RUN",
        "TST-UNKNOWN",
        "TST-ALREADY-ID",
        "TST-ALREADY-NAME",
        "TST-ALREADY-TITLE",
    ]


def test_rf16_keeps_allowed_recommended_tests_when_executed_tests_are_missing() -> None:
    recommended = [
        "TST-ALLOWED-STRING",
        {"test_id": "TST-KEEP", "rationale": "Cobertura adicional"},
    ]

    filtered, removed = second_level_module._filter_recommended_tests_against_executed(
        recommended_tests=recommended,
        executed_test_ids=[],
        available_tests_not_executed=[
            {"test_id": "TST-ALLOWED-STRING"},
            {"test_id": "TST-KEEP"},
        ],
    )

    assert filtered == recommended
    assert removed == []


def test_rf16_recommended_test_filter_does_not_touch_other_item_types() -> None:
    actions = [{"action": "Revisar entidad concreta", "why": "Riesgo alto"}]
    procedures = [{"procedure": "Contrastar documento", "why": "Evidencia disponible"}]

    filtered, removed = second_level_module._filter_recommended_tests_against_executed(
        recommended_tests=[{"test_id": "TST-EXECUTED"}, {"test_id": "TST-NEW"}],
        executed_test_ids=["TST-EXECUTED"],
        available_tests_not_executed=[{"test_id": "TST-NEW"}],
    )

    assert filtered == [{"test_id": "TST-NEW"}]
    assert removed == ["TST-EXECUTED"]
    assert actions == [{"action": "Revisar entidad concreta", "why": "Riesgo alto"}]
    assert procedures == [{"procedure": "Contrastar documento", "why": "Evidencia disponible"}]


def test_rf16_drops_all_recommended_tests_when_no_candidates_are_available() -> None:
    filtered, removed = second_level_module._filter_recommended_tests_against_executed(
        recommended_tests=["TST-ANY", {"test_id": "TST-OTHER"}],
        executed_test_ids=["TST-ANY"],
        available_tests_not_executed=[],
    )

    assert filtered == []
    assert removed == ["TST-ANY", "TST-OTHER"]


def test_rf16_recommended_tests_fallback_uses_only_catalog_candidates() -> None:
    fallback = second_level_module._fallback_recommended_tests_from_candidates(
        available_tests_not_executed=[
            {"test_id": "TST-NEW-1", "fraud_type": "amount_anomaly", "title": "Importes atípicos"},
            {"test_id": "TST-NEW-2", "fraud_type": "duplicate_entry"},
            {"test_id": "TST-NEW-3"},
            {"test_id": "TST-NEW-4"},
        ],
        max_items=3,
    )

    assert [row["test_id"] for row in fallback] == ["TST-NEW-1", "TST-NEW-2", "TST-NEW-3"]
    assert all(row["source"] == "deterministic_available_not_executed_fallback" for row in fallback)
    assert all(row["rationale"] for row in fallback)
