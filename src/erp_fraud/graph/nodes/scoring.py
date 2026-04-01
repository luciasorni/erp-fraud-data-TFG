"""Nodo scoring y validador de scoring."""

from __future__ import annotations

from typing import Any

from ..state import GraphState
from . import _legacy


def scoring_node(state: GraphState) -> GraphState:
    return _legacy.scoring_node(state)


def validate_scoring_evidence_and_probability_sum(output: Any, input_payload: dict[str, Any]) -> dict[str, Any]:
    return _legacy._validate_scoring_evidence_and_probability_sum(output, input_payload)
