"""Estado compartido del grafo multiagente (RF14-01)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class GraphState:
    """Estado canónico del flujo RF14.

    Campos exigidos por backlog RF14-01:
    - schema
    - kb_status
    - hypotheses
    - selected_tests
    - findings
    - explanations
    - scores
    - run_metadata
    """

    run_id: str
    schema: dict[str, Any] = field(default_factory=dict)
    kb_status: dict[str, Any] = field(default_factory=dict)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    selected_tests: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    explanations: list[dict[str, Any]] = field(default_factory=list)
    scores: list[dict[str, Any]] = field(default_factory=list)
    run_metadata: dict[str, Any] = field(default_factory=dict)


def create_initial_graph_state(
    *,
    run_id: str,
    dataset_hash: str = "",
    input_zip: str = "",
) -> GraphState:
    """Construye estado inicial con defaults estables para un run."""
    resolved_run_id = str(run_id).strip()
    if not resolved_run_id:
        raise ValueError("run_id debe ser string no vacío")

    metadata: dict[str, Any] = {
        "run_id": resolved_run_id,
        "dataset_hash": str(dataset_hash).strip(),
        "input_zip": str(input_zip).strip(),
        "created_at_utc": _utc_now_iso(),
        "updated_at_utc": _utc_now_iso(),
        "node_status": {},
        "node_timings_ms": {},
        "errors": [],
    }
    kb_status = {
        "status": "PENDING",
        "index_manifest_path": "",
        "chunks_indexed": 0,
        "sources_used": 0,
        "error": "",
    }
    return GraphState(run_id=resolved_run_id, kb_status=kb_status, run_metadata=metadata)


def graph_state_to_dict(state: GraphState) -> dict[str, Any]:
    """Serializa el estado a `dict` (útil para logs/artefactos)."""
    payload = asdict(state)
    payload["run_metadata"]["updated_at_utc"] = _utc_now_iso()
    return payload

