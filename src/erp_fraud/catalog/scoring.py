"""Scoring base para RF07-02: score_test = weight * metric."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _as_float(value: Any, *, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} debe ser numérico (valor={value!r})") from exc
    return parsed


def load_weights_config(path: str | Path = "config/weights.yaml") -> dict[str, Any]:
    """Carga y valida mínimamente el fichero weights.yaml."""
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"No existe config de pesos: {resolved}")
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("No se puede leer YAML sin PyYAML instalado") from exc

    payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("weights.yaml debe contener un objeto raíz")

    ranking_cfg = payload.get("ranking", {})
    if ranking_cfg is not None and not isinstance(ranking_cfg, dict):
        raise ValueError("weights.yaml: 'ranking' debe ser objeto")
    if isinstance(ranking_cfg, dict) and "top_k" in ranking_cfg:
        top_k_value = ranking_cfg.get("top_k")
        try:
            parsed_top_k = int(top_k_value)
        except (TypeError, ValueError) as exc:
            raise ValueError("weights.yaml: 'ranking.top_k' debe ser entero > 0") from exc
        if isinstance(top_k_value, bool) or parsed_top_k <= 0:
            raise ValueError("weights.yaml: 'ranking.top_k' debe ser entero > 0")

    defaults = payload.get("defaults")
    if not isinstance(defaults, dict):
        raise ValueError("weights.yaml: falta objeto 'defaults'")
    severity_weights = defaults.get("severity_weights")
    if not isinstance(severity_weights, dict):
        raise ValueError("weights.yaml: falta 'defaults.severity_weights'")
    fallback_weight = defaults.get("fallback_weight")
    _as_float(fallback_weight, field_name="defaults.fallback_weight")

    overrides = payload.get("overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("weights.yaml: 'overrides' debe ser objeto")
    by_test_id = overrides.get("by_test_id", {})
    if not isinstance(by_test_id, dict):
        raise ValueError("weights.yaml: 'overrides.by_test_id' debe ser objeto")

    return payload


def resolve_ranking_top_k(
    *,
    weights_config: dict[str, Any],
    default_top_k: int = 20,
) -> int:
    """Resuelve top-k de ranking desde config con fallback seguro."""
    ranking_cfg = weights_config.get("ranking", {})
    if isinstance(ranking_cfg, dict) and "top_k" in ranking_cfg:
        value = ranking_cfg.get("top_k")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"ranking.top_k debe ser entero > 0 (valor={value!r})") from exc
        if parsed <= 0:
            raise ValueError(f"ranking.top_k debe ser > 0 (valor={value!r})")
        return parsed
    return int(default_top_k)


def resolve_test_weight(
    *,
    weights_config: dict[str, Any],
    test_id: str,
    severity: str | None = None,
) -> float:
    """Resuelve peso por prioridad: override test_id > severity > fallback."""
    overrides = (
        weights_config.get("overrides", {})
        .get("by_test_id", {})
    )
    if isinstance(overrides, dict):
        candidate = overrides.get(test_id)
        if isinstance(candidate, dict) and "weight" in candidate:
            return _as_float(candidate["weight"], field_name=f"overrides.by_test_id.{test_id}.weight")

    defaults = weights_config.get("defaults", {})
    severity_weights = defaults.get("severity_weights", {})
    if severity and isinstance(severity_weights, dict) and severity in severity_weights:
        return _as_float(
            severity_weights[severity],
            field_name=f"defaults.severity_weights.{severity}",
        )

    return _as_float(defaults.get("fallback_weight"), field_name="defaults.fallback_weight")


def extract_metric_value(metrics: dict[str, Any] | None) -> float:
    """Extrae una métrica escalar para scoring con reglas simples.

    Prioridad actual:
    1. duplicate_count
    2. z_score (valor absoluto)
    3. amount_score
    4. fallback = 1.0
    """
    if not isinstance(metrics, dict) or not metrics:
        return 1.0

    if "duplicate_count" in metrics:
        return max(0.0, _as_float(metrics["duplicate_count"], field_name="metrics.duplicate_count"))
    if "z_score" in metrics:
        return abs(_as_float(metrics["z_score"], field_name="metrics.z_score"))
    if "amount_score" in metrics:
        return max(0.0, _as_float(metrics["amount_score"], field_name="metrics.amount_score"))
    return 1.0


def compute_score_test(
    *,
    weights_config: dict[str, Any],
    test_id: str,
    metrics: dict[str, Any] | None,
    severity: str | None = None,
) -> dict[str, float]:
    """Calcula score_test = weight * metric."""
    weight = resolve_test_weight(
        weights_config=weights_config,
        test_id=test_id,
        severity=severity,
    )
    metric_value = extract_metric_value(metrics)
    score_test = weight * metric_value
    return {
        "weight": float(weight),
        "metric_value": float(metric_value),
        "score_test": float(score_test),
    }
