"""Definición mínima de flujo grafo RF14 (stubs)."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from .nodes import run_node_by_id
from .observability import append_error_event
from .state import GraphState, create_initial_graph_state


DEFAULT_GRAPH_SEQUENCE_STUB: tuple[str, ...] = (
    "hypothesis_planner",
    "test_planner",
    "executor",
    "explainer",
    "scoring",
)

# Alias retrocompatible para tests/código previo.
DEFAULT_GRAPH_SEQUENCE: tuple[str, ...] = DEFAULT_GRAPH_SEQUENCE_STUB


DEFAULT_GRAPH_SEQUENCE_FULL: tuple[str, ...] = (
    "ingest",
    "kb_index",
    "hypothesis_planner",
    "test_planner",
    "executor",
    "explainer",
    "scoring",
    "persist",
)


@dataclass(frozen=True)
class NodeExecutionPolicy:
    timeout_ms: int
    retries: int


def _meta(state: GraphState) -> dict[str, Any]:
    return state.run_metadata if isinstance(state.run_metadata, dict) else {}


def _resolve_node_execution_policy(*, state: GraphState, node_id: str) -> NodeExecutionPolicy:
    metadata = _meta(state)

    default_timeout_ms = int(metadata.get("graph_default_timeout_ms", 30000) or 30000)
    default_retries = int(metadata.get("graph_default_retries", 0) or 0)
    timeout_by_node = metadata.get("graph_node_timeouts_ms", {})
    retries_by_node = metadata.get("graph_node_retries", {})

    timeout_ms = default_timeout_ms
    retries = default_retries
    if isinstance(timeout_by_node, dict) and node_id in timeout_by_node:
        timeout_ms = int(timeout_by_node.get(node_id, default_timeout_ms) or default_timeout_ms)
    if isinstance(retries_by_node, dict) and node_id in retries_by_node:
        retries = int(retries_by_node.get(node_id, default_retries) or default_retries)

    if timeout_ms <= 0:
        timeout_ms = default_timeout_ms if default_timeout_ms > 0 else 30000
    if retries < 0:
        retries = 0
    return NodeExecutionPolicy(timeout_ms=timeout_ms, retries=retries)


def _record_node_attempt(
    *,
    state: GraphState,
    node_id: str,
    attempt: int,
    duration_ms: int,
    status: str,
    error: str = "",
) -> None:
    metadata = _meta(state)
    node_attempts = metadata.setdefault("node_attempts", {})
    if isinstance(node_attempts, dict):
        node_attempts[node_id] = int(attempt)

    node_status = metadata.setdefault("node_status", {})
    if isinstance(node_status, dict):
        node_status[node_id] = status

    node_timings = metadata.setdefault("node_timings_ms", {})
    if isinstance(node_timings, dict):
        node_timings[node_id] = int(duration_ms)

    if error:
        append_error_event(
            run_metadata=metadata,
            node_id=node_id,
            status=status,
            error=error,
            attempt=attempt,
            phase="graph_runner",
        )


def _execute_node_with_policy(
    *,
    state: GraphState,
    node_id: str,
) -> GraphState:
    policy = _resolve_node_execution_policy(state=state, node_id=node_id)
    last_error: Exception | None = None

    for attempt in range(1, policy.retries + 2):
        started = perf_counter()
        try:
            result_state = run_node_by_id(node_id=node_id, state=state)
        except Exception as exc:
            elapsed_ms = int((perf_counter() - started) * 1000)
            last_error = exc
            if attempt <= policy.retries:
                _record_node_attempt(
                    state=state,
                    node_id=node_id,
                    attempt=attempt,
                    duration_ms=elapsed_ms,
                    status="ERROR_RETRY",
                    error=f"{type(exc).__name__}: {exc}",
                )
                continue
            _record_node_attempt(
                state=state,
                node_id=node_id,
                attempt=attempt,
                duration_ms=elapsed_ms,
                status="ERROR",
                error=f"{type(exc).__name__}: {exc}",
            )
            raise exc

        elapsed_ms = int((perf_counter() - started) * 1000)
        if elapsed_ms > policy.timeout_ms:
            timeout_exc = TimeoutError(f"{node_id} excedió timeout_ms={policy.timeout_ms}")
            last_error = timeout_exc
            if attempt <= policy.retries:
                _record_node_attempt(
                    state=state,
                    node_id=node_id,
                    attempt=attempt,
                    duration_ms=elapsed_ms,
                    status="TIMEOUT_RETRY",
                    error=str(timeout_exc),
                )
                continue
            _record_node_attempt(
                state=state,
                node_id=node_id,
                attempt=attempt,
                duration_ms=elapsed_ms,
                status="TIMEOUT",
                error=str(timeout_exc),
            )
            raise timeout_exc

        _record_node_attempt(
            state=result_state,
            node_id=node_id,
            attempt=attempt,
            duration_ms=elapsed_ms,
            status="OK",
        )
        return result_state

    if last_error is not None:  # pragma: no cover
        raise last_error
    return state


def _should_abort_before_planning(state: GraphState) -> bool:
    metadata = _meta(state)
    if bool(metadata.get("abort_graph", False)):
        return True
    if str(metadata.get("ingest_status", "")).strip().upper() == "ERROR":
        return True
    if bool(metadata.get("schema_validation_failed", False)):
        return True
    return False


def _mark_graph_abort(state: GraphState, *, reason: str) -> None:
    metadata = _meta(state)
    metadata["graph_status"] = "ABORTED"
    metadata["graph_abort_reason"] = reason
    node_status = metadata.setdefault("node_status", {})
    if isinstance(node_status, dict):
        node_status["graph_router"] = "ABORTED"
    errors = metadata.setdefault("errors", [])
    if isinstance(errors, list):
        append_error_event(
            run_metadata=metadata,
            node_id="graph_router",
            status="ABORTED",
            error=reason,
            phase="graph_router",
        )


def run_graph(
    *,
    initial_state: GraphState,
    sequence: tuple[str, ...] = DEFAULT_GRAPH_SEQUENCE_FULL,
) -> GraphState:
    """Ejecuta grafo con routing condicional + timeout/retry por nodo (RF14-12)."""
    state = initial_state
    for node_id in sequence:
        if node_id != "persist" and _should_abort_before_planning(state):
            _mark_graph_abort(state, reason="precondition_failed_before_planning")
            if "persist" in sequence:
                state = _execute_node_with_policy(state=state, node_id="persist")
            return state
        try:
            state = _execute_node_with_policy(state=state, node_id=node_id)
        except Exception as exc:
            _mark_graph_abort(state, reason=f"node_failed:{node_id}:{type(exc).__name__}")
            if node_id != "persist" and "persist" in sequence:
                try:
                    state = _execute_node_with_policy(state=state, node_id="persist")
                except Exception:
                    pass
            return state

    metadata = _meta(state)
    if str(metadata.get("graph_status", "")).strip().upper() != "ABORTED":
        metadata["graph_status"] = "OK"
    return state


def run_graph_stub(
    *,
    run_id: str,
    dataset_hash: str = "",
    input_zip: str = "",
    sequence: tuple[str, ...] = DEFAULT_GRAPH_SEQUENCE_STUB,
) -> GraphState:
    """Ejecuta secuencia lineal de nodos stub y devuelve estado final."""
    state = create_initial_graph_state(
        run_id=run_id,
        dataset_hash=dataset_hash,
        input_zip=input_zip,
    )
    return run_graph(initial_state=state, sequence=sequence)


def run_graph_full(
    *,
    run_id: str,
    dataset_hash: str = "",
    input_zip: str = "",
    run_metadata_overrides: dict[str, Any] | None = None,
) -> GraphState:
    """Ejecuta el flujo completo RF14 con ingest+kb+persist."""
    state = create_initial_graph_state(
        run_id=run_id,
        dataset_hash=dataset_hash,
        input_zip=input_zip,
    )
    if isinstance(run_metadata_overrides, dict):
        state.run_metadata.update(run_metadata_overrides)
    return run_graph(initial_state=state, sequence=DEFAULT_GRAPH_SEQUENCE_FULL)
