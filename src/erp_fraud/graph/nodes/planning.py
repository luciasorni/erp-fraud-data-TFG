"""Nodos de planificación (hipótesis/tests) y validadores."""

from __future__ import annotations

from typing import Any

from ..state import GraphState
from . import _legacy


def hypothesis_planner_node(state: GraphState) -> GraphState:
    return _legacy.hypothesis_planner_node(state)


def test_planner_node(state: GraphState) -> GraphState:
    return _legacy.test_planner_node(state)


def validate_hypotheses_output(output: Any, input_payload: dict[str, Any]) -> dict[str, Any]:
    return _legacy._validate_hypotheses_output(output, input_payload)
