"""Nodo de persistencia de artefactos del grafo."""

from __future__ import annotations

from ..state import GraphState
from . import _legacy


def persist_node(state: GraphState) -> GraphState:
    return _legacy.persist_node(state)
