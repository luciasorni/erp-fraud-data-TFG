"""Estado compartido del grafo multiagente (RF14-01)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

GRAPH_STATE_SCHEMA_VERSION = "1.0.0"
GRAPH_STATE_REQUIRED_FIELDS: tuple[str, ...] = (
    "run_id",
    "schema",
    "kb_status",
    "hypotheses",
    "selected_tests",
    "findings",
    "test_runs",
    "ranking",
    "fraud_type_predicho",
    "recomendaciones",
    "export_paths",
    "explanations",
    "scores",
    "run_metadata",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class GraphState:
    """Estado canónico del flujo RF14/RF15c.

    Campos exigidos por backlog RF14-01:
    - schema
    - kb_status
    - hypotheses
    - selected_tests
    - findings
    - explanations
    - scores
    - run_metadata

    Extensiones RF15c-01:
    - test_runs
    - ranking
    - fraud_type_predicho
    - recomendaciones
    - export_paths
    """

    run_id: str
    schema: dict[str, Any] = field(default_factory=dict)
    kb_status: dict[str, Any] = field(default_factory=dict)
    hypotheses: list[dict[str, Any]] = field(default_factory=list)
    selected_tests: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    test_runs: list[dict[str, Any]] = field(default_factory=list)
    ranking: list[dict[str, Any]] = field(default_factory=list)
    fraud_type_predicho: list[dict[str, Any]] = field(default_factory=list)
    recomendaciones: list[dict[str, Any]] = field(default_factory=list)
    export_paths: dict[str, Any] = field(default_factory=dict)
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
        "llm_mode": "stub",
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


def get_graph_state_contract() -> dict[str, Any]:
    """Contrato congelado de GraphState para compatibilidad retro."""
    return {
        "schema_version": GRAPH_STATE_SCHEMA_VERSION,
        "required_fields": list(GRAPH_STATE_REQUIRED_FIELDS),
    }


def validate_graph_state_payload(payload: dict[str, Any]) -> list[str]:
    """Valida campos mínimos requeridos del estado serializado."""
    if not isinstance(payload, dict):
        return ["GraphState payload debe ser objeto"]
    missing = [field for field in GRAPH_STATE_REQUIRED_FIELDS if field not in payload]
    return [f"missing_field:{field}" for field in missing]
