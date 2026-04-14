from __future__ import annotations

import json
from pathlib import Path

from src.erp_fraud.storage.run_metadata import write_run_metadata_json


def test_rf14c09_run_metadata_includes_artifact_hash_and_process_scope(tmp_path: Path) -> None:
    output = tmp_path / "run_results" / "rf14c09-run" / "run_metadata.json"
    write_run_metadata_json(
        output,
        run_id="rf14c09-run",
        dataset_hash="dataset-hash",
        process_family="p2p",
        process_scope="both",
        artifact_hash="artifact-hash-123",
        project_root=tmp_path,
        code_version="code",
        tests_version="tests",
        config_version="config",
        timestamp_utc="2026-04-14T00:00:00+00:00",
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["artifact_hash"] == "artifact-hash-123"
    assert payload["process_scope"] == "both"

