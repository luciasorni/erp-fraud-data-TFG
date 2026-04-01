"""Nodos de ingest y KB index."""

from __future__ import annotations

from ..state import GraphState
from . import _legacy


def ingest_node(state: GraphState) -> GraphState:
    return _legacy.ingest_node(state)


def kb_index_node(state: GraphState) -> GraphState:
    return _legacy.kb_index_node(state)
