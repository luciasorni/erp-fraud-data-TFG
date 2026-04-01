"""Nodos del grafo RF14/RF15 organizados por módulo.

Este paquete mantiene compatibilidad con el API histórico `src.erp_fraud.graph.nodes`
para no romper imports/tests mientras se completa la migración.
"""

from __future__ import annotations

from typing import Any

from . import _legacy
from .executor import executor_node as _executor_node_impl
from .explainer import (
    explainer_node as _explainer_node_impl,
    expert_explainer_node as _expert_explainer_node_impl,
    validate_explanations_guardrails as _validate_explanations_guardrails_impl,
)
from .ingest import ingest_node as _ingest_node_impl
from .ingest import kb_index_node as _kb_index_node_impl
from .persist import persist_node as _persist_node_impl
from .planning import (
    hypothesis_planner_node as _hypothesis_planner_node_impl,
    test_planner_node as _test_planner_node_impl,
    validate_hypotheses_output as _validate_hypotheses_output_impl,
)
from .registry import run_node_by_id as _run_node_by_id_impl
from .scoring import (
    scoring_node as _scoring_node_impl,
    validate_scoring_evidence_and_probability_sum as _validate_scoring_evidence_and_probability_sum_impl,
)

# Dependencias parcheables en tests (compatibilidad retroactiva).
KBSearchTool = _legacy.KBSearchTool
TestRunner = _legacy.TestRunner
build_kb_index = _legacy.build_kb_index
alpha_loop = _legacy.alpha_loop
alpha_loop_result_to_dict = _legacy.alpha_loop_result_to_dict
_tool_test_catalog = _legacy._tool_test_catalog


def _sync_legacy_dependencies() -> None:
    _legacy.KBSearchTool = KBSearchTool
    _legacy.TestRunner = TestRunner
    _legacy.build_kb_index = build_kb_index
    _legacy.alpha_loop = alpha_loop
    _legacy.alpha_loop_result_to_dict = alpha_loop_result_to_dict
    _legacy._tool_test_catalog = _tool_test_catalog


def ingest_node(state):
    _sync_legacy_dependencies()
    return _ingest_node_impl(state)


def kb_index_node(state):
    _sync_legacy_dependencies()
    return _kb_index_node_impl(state)


def hypothesis_planner_node(state):
    _sync_legacy_dependencies()
    return _hypothesis_planner_node_impl(state)


def test_planner_node(state):
    _sync_legacy_dependencies()
    return _test_planner_node_impl(state)

# Evita que pytest intente colectar esta función como test por su prefijo.
test_planner_node.__test__ = False  # type: ignore[attr-defined]


def executor_node(state):
    _sync_legacy_dependencies()
    return _executor_node_impl(state)


def explainer_node(state):
    _sync_legacy_dependencies()
    return _explainer_node_impl(state)


def expert_explainer_node(state):
    _sync_legacy_dependencies()
    return _expert_explainer_node_impl(state)


def scoring_node(state):
    _sync_legacy_dependencies()
    return _scoring_node_impl(state)


def persist_node(state):
    _sync_legacy_dependencies()
    return _persist_node_impl(state)


def run_node_by_id(*, node_id: str, state):
    _sync_legacy_dependencies()
    return _run_node_by_id_impl(node_id=node_id, state=state)


# Validadores expuestos para tests RF14/RF15/RF15c.
def _validate_hypotheses_output(output: Any, input_payload: dict[str, Any]) -> dict[str, Any]:
    _sync_legacy_dependencies()
    return _validate_hypotheses_output_impl(output, input_payload)


def _validate_explanations_guardrails(
    *, explanations: list[dict], findings: list[dict], catalog_test_ids=None, schema_columns=None
):
    _sync_legacy_dependencies()
    return _validate_explanations_guardrails_impl(
        explanations=explanations,
        findings=findings,
        catalog_test_ids=catalog_test_ids,
        schema_columns=schema_columns,
    )


def _validate_scoring_evidence_and_probability_sum(
    output: Any, input_payload: dict[str, Any]
) -> dict[str, Any]:
    _sync_legacy_dependencies()
    return _validate_scoring_evidence_and_probability_sum_impl(output, input_payload)


__all__ = [
    "KBSearchTool",
    "TestRunner",
    "alpha_loop",
    "alpha_loop_result_to_dict",
    "build_kb_index",
    "executor_node",
    "expert_explainer_node",
    "explainer_node",
    "hypothesis_planner_node",
    "ingest_node",
    "kb_index_node",
    "persist_node",
    "run_node_by_id",
    "scoring_node",
    "test_planner_node",
    "_tool_test_catalog",
    "_validate_explanations_guardrails",
    "_validate_hypotheses_output",
    "_validate_scoring_evidence_and_probability_sum",
]
