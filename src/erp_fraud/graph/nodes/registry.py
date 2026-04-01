"""Dispatcher de nodos por ID."""

from __future__ import annotations

from ..state import GraphState
from . import _legacy


def run_node_by_id(*, node_id: str, state: GraphState) -> GraphState:
    return _legacy.run_node_by_id(node_id=node_id, state=state)
