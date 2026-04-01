"""Nodo ejecutor."""

from __future__ import annotations

from ..state import GraphState
from . import _legacy


def executor_node(state: GraphState) -> GraphState:
    return _legacy.executor_node(state)
