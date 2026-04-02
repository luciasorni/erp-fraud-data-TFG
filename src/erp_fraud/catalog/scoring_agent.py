"""ScoringAgent RF18: genera y valida salida ScoreSchema."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .score_schema import SCORE_SCHEMA_REQUIRED_FIELDS, SCORE_SCHEMA_VERSION


def _utc_now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_models_config(path: str | Path = "config/models.yaml") -> dict[str, Any]:
    """Carga configuración de modelos para scoring."""
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"No existe config de modelos: {resolved}")
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("No se puede leer YAML sin PyYAML instalado") from exc

    payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("models.yaml debe contener un objeto raíz")
    scoring = payload.get("scoring", {})
    if not isinstance(scoring, dict):
        raise ValueError("models.yaml: 'scoring' debe ser objeto")
    profiles = scoring.get("profiles", {})
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError("models.yaml: 'scoring.profiles' debe ser objeto no vacío")
    return payload


def resolve_scoring_model(
    *,
    models_config: dict[str, Any],
    profile: str | None,
) -> dict[str, Any]:
    """Resuelve perfil de scoring desde models.yaml con fallback seguro."""
    defaults = models_config.get("defaults", {})
    if not isinstance(defaults, dict):
        defaults = {}
    default_profile = str(defaults.get("scoring_profile", "default")).strip() or "default"
    requested_profile = str(profile or "").strip() or default_profile

    scoring = models_config.get("scoring", {})
    profiles = scoring.get("profiles", {}) if isinstance(scoring, dict) else {}
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError("models.yaml inválido: falta scoring.profiles")

    selected = profiles.get(requested_profile)
    if not isinstance(selected, dict):
        selected = profiles.get(default_profile)
    if not isinstance(selected, dict):
        selected = next((v for v in profiles.values() if isinstance(v, dict)), None)
    if not isinstance(selected, dict):
        raise ValueError(f"No se pudo resolver perfil de scoring: {requested_profile}")

    model_used = str(selected.get("model_used", "")).strip()
    if not model_used:
        raise ValueError(f"Perfil de scoring sin model_used: {requested_profile}")
    return {
        "profile": requested_profile if requested_profile in profiles else default_profile,
        "model_used": model_used,
        "temperature": _safe_float(selected.get("temperature", 0.0)),
        "max_tokens": int(selected.get("max_tokens", 0) or 0),
    }


class ScoringAgent:
    """Agente de scoring con contrato estable (ScoreSchema)."""

    def __init__(self, *, model_used: str = "scoring-deterministic-v2") -> None:
        self.model_used = str(model_used).strip() or "scoring-deterministic-v2"

    def generate(
        self,
        *,
        hypotheses: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        acfe_snippets: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Genera un payload ScoreSchema a partir de hipótesis + hallazgos + ACFE."""
        _ = hypotheses, acfe_snippets

        by_fraud_type: dict[str, dict[str, Any]] = {}
        for row in findings:
            if not isinstance(row, dict):
                continue
            fraud_type = str(row.get("fraud_type", "")).strip()
            test_id = str(row.get("test_id", "")).strip()
            finding_count = int(row.get("finding_count", 0) or 0)
            if not fraud_type:
                continue
            entry = by_fraud_type.setdefault(
                fraud_type,
                {"support": 0, "source_test_ids": set()},
            )
            entry["support"] = int(entry["support"]) + max(0, finding_count)
            if test_id:
                entry["source_test_ids"].add(test_id)

        total_support = sum(int(item["support"]) for item in by_fraud_type.values())
        fraud_type_probs: list[dict[str, Any]] = []
        for fraud_type in sorted(by_fraud_type.keys()):
            support = int(by_fraud_type[fraud_type]["support"])
            probability = float(support) / float(total_support) if total_support > 0 else 0.0
            fraud_type_probs.append(
                {
                    "fraud_type": fraud_type,
                    "probability": probability,
                    "source_test_ids": sorted(by_fraud_type[fraud_type]["source_test_ids"]),
                }
            )

        if fraud_type_probs:
            winner = max(fraud_type_probs, key=lambda row: _safe_float(row.get("probability", 0.0)))
            final_label = str(winner.get("fraud_type", "")).strip()
            confidence = _safe_float(winner.get("probability", 0.0))
        else:
            final_label = "unknown"
            confidence = 0.0

        referenced_tests = sorted(
            {
                str(test_id).strip()
                for row in fraud_type_probs
                if isinstance(row, dict)
                for test_id in row.get("source_test_ids", [])
                if str(test_id).strip()
            }
        )
        if referenced_tests:
            evidence_summary = f"Evidence from tests: {', '.join(referenced_tests)}"
        else:
            evidence_summary = "No findings available for scoring."

        return {
            "score_schema_version": SCORE_SCHEMA_VERSION,
            "generated_at_utc": _utc_now_iso_z(),
            "fraud_type_probs": fraud_type_probs,
            "final_label": final_label,
            "confidence": confidence,
            "evidence_summary": evidence_summary,
            "model_used": self.model_used,
        }

    def parse_output(self, raw_output: Any) -> dict[str, Any]:
        """Parsea/normaliza salida cruda a ScoreSchema y valida campos mínimos."""
        if isinstance(raw_output, list):
            raw_output = raw_output[0] if raw_output else {}
        if not isinstance(raw_output, dict):
            raise ValueError("score output debe ser objeto JSON")

        missing = [field for field in SCORE_SCHEMA_REQUIRED_FIELDS if field not in raw_output]
        if missing:
            raise ValueError(f"score output incompleto, faltan campos: {missing}")

        parsed = dict(raw_output)
        parsed["score_schema_version"] = str(parsed.get("score_schema_version", "")).strip() or SCORE_SCHEMA_VERSION
        parsed["generated_at_utc"] = str(parsed.get("generated_at_utc", "")).strip() or _utc_now_iso_z()
        parsed["final_label"] = str(parsed.get("final_label", "")).strip() or "unknown"
        parsed["confidence"] = _safe_float(parsed.get("confidence", 0.0))
        parsed["evidence_summary"] = str(parsed.get("evidence_summary", "")).strip()
        parsed["model_used"] = str(parsed.get("model_used", "")).strip() or self.model_used

        probs = parsed.get("fraud_type_probs", [])
        if not isinstance(probs, list):
            raise ValueError("fraud_type_probs debe ser lista")
        normalized_probs: list[dict[str, Any]] = []
        for row in probs:
            if not isinstance(row, dict):
                continue
            fraud_type = str(row.get("fraud_type", "")).strip()
            if not fraud_type:
                continue
            normalized_row = dict(row)
            normalized_row["fraud_type"] = fraud_type
            normalized_row["probability"] = _safe_float(row.get("probability", 0.0))
            source_test_ids = row.get("source_test_ids", [])
            if not isinstance(source_test_ids, list):
                source_test_ids = []
            normalized_row["source_test_ids"] = sorted(
                {str(test_id).strip() for test_id in source_test_ids if str(test_id).strip()}
            )
            normalized_probs.append(normalized_row)
        parsed["fraud_type_probs"] = normalized_probs
        return parsed
