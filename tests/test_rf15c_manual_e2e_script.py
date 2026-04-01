from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from scripts.run_rf15c_e2e_manual import (
    build_rf15c_14_evidence_payload,
    resolve_langsmith_snapshot,
)


def test_rf15c_14_evidence_payload_contains_required_fields() -> None:
    snapshot = resolve_langsmith_snapshot(explicit_trace_link="https://smith.langchain.com/public/trace")
    payload = build_rf15c_14_evidence_payload(
        run_id="rf15c14-test",
        run_metadata={
            "graph_status": "OK",
            "node_status": {"executor": "OK"},
            "persist_manifest_path": "run_results/rf15c14-test/graph/manifest.json",
            "persist_artifacts": {"score_json": "run_results/rf15c14-test/graph/score.json"},
        },
        langsmith=snapshot,
        llm_mode="stub",
        notes="manual evidence",
    )
    assert payload["rf_task"] == "RF15c-14"
    assert payload["run_id"] == "rf15c14-test"
    assert payload["graph_status"] == "OK"
    assert payload["langsmith"]["trace_link"] == "https://smith.langchain.com/public/trace"
    assert payload["llm_mode"] == "stub"
    assert "score_json" in payload["persist_artifacts"]

