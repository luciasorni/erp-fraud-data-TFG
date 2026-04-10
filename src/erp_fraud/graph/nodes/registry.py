"""Dispatcher de nodos por ID."""

from __future__ import annotations

from ..state import GraphState
from .executor import executor_node
from .explainer import expert_explainer_node, explainer_node
from .ingest import ingest_node, kb_index_node
from .persist import persist_node
from .planning import hypothesis_planner_node, test_planner_node
from .scoring import scoring_node
from .second_level_explainer import second_level_explainer_node

_NODE_DISPATCH = {
    "hypothesis_planner": hypothesis_planner_node,
    "ingest": ingest_node,
    "kb_index": kb_index_node,
    "test_planner": test_planner_node,
    "executor": executor_node,
    "expert_explainer": expert_explainer_node,
    "explainer": explainer_node,
    "scoring": scoring_node,
    "persist": persist_node,
    "second_level_explainer": second_level_explainer_node,
}


def run_node_by_id(*, node_id: str, state: GraphState) -> GraphState:
    fn = _NODE_DISPATCH.get(node_id)
    if fn is None:
        raise ValueError(f"Unknown graph node_id: {node_id}")
    return fn(state)
