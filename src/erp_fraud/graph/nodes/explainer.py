"""Nodo explicador y validadores de guardrails."""

from __future__ import annotations

from ..state import GraphState
from . import _legacy


def explainer_node(state: GraphState) -> GraphState:
    return _legacy.explainer_node(state)


def expert_explainer_node(state: GraphState) -> GraphState:
    return _legacy.expert_explainer_node(state)


def validate_explanations_guardrails(*, explanations: list[dict], findings: list[dict], catalog_test_ids=None, schema_columns=None):
    return _legacy._validate_explanations_guardrails(
        explanations=explanations,
        findings=findings,
        catalog_test_ids=catalog_test_ids,
        schema_columns=schema_columns,
    )
