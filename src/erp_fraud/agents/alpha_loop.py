"""Bucle reusable Plan->Draft->Validate->Repair para nodos AlphaCodium (AG03-08)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from ..storage.paths import ruta_run


ValidatorFn = Callable[[Any, dict[str, Any]], Any]
GenerateFn = Callable[[str, dict[str, Any], list[str], int], Any]


def _utc_timestamp_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _serialize_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def _normalize_validator_result(name: str, value: Any) -> dict[str, Any]:
    """Normaliza resultados heterogéneos de validadores a un shape común."""
    if isinstance(value, bool):
        return {"name": name, "passed": bool(value), "errors": []}

    if isinstance(value, dict):
        passed = bool(value.get("passed", False))
        errors = value.get("errors", [])
        if isinstance(errors, str):
            errors = [errors]
        if not isinstance(errors, list):
            errors = [str(errors)]
        return {
            "name": name,
            "passed": passed,
            "errors": [str(err) for err in errors],
            "detail": value.get("detail"),
        }

    if isinstance(value, tuple) and len(value) == 2:
        passed_raw, errors_raw = value
        passed = bool(passed_raw)
        if isinstance(errors_raw, str):
            errors = [errors_raw]
        elif isinstance(errors_raw, list):
            errors = [str(err) for err in errors_raw]
        else:
            errors = [str(errors_raw)] if errors_raw else []
        return {"name": name, "passed": passed, "errors": errors}

    return {"name": name, "passed": False, "errors": [f"{name}: resultado inválido de validador"]}


@dataclass(frozen=True)
class AlphaLoopResult:
    status: str
    run_id: str
    node_id: str
    iterations: int
    final_output: Any
    last_validation: dict[str, Any]
    artifacts_dir: str


def alpha_loop(
    *,
    run_id: str,
    node_id: str,
    prompt_text: str,
    input_payload: dict[str, Any],
    generate_fn: GenerateFn,
    validators: dict[str, ValidatorFn],
    max_iter: int = 3,
) -> AlphaLoopResult:
    """Ejecuta bucle Plan->Draft->Validate->Repair con persistencia de iteraciones."""
    if not run_id or not run_id.strip():
        raise ValueError("run_id debe ser string no vacío")
    if not node_id or not node_id.strip():
        raise ValueError("node_id debe ser string no vacío")
    if not isinstance(prompt_text, str) or not prompt_text.strip():
        raise ValueError("prompt_text debe ser string no vacío")
    if not isinstance(input_payload, dict):
        raise TypeError("input_payload debe ser dict")
    if not callable(generate_fn):
        raise TypeError("generate_fn debe ser callable")
    if not isinstance(validators, dict) or not validators:
        raise ValueError("validators debe ser dict no vacío")
    if not isinstance(max_iter, int) or max_iter <= 0:
        raise ValueError("max_iter debe ser int > 0")

    node_dir = ruta_run(run_id) / "alphacodium" / node_id
    manifest_path = node_dir / "iterations_manifest.jsonl"

    repair_feedback: list[str] = []
    final_output: Any = None
    last_validation: dict[str, Any] = {}

    for iteration in range(1, max_iter + 1):
        iteration_dir = node_dir / f"iteration_{iteration:03d}"
        iteration_dir.mkdir(parents=True, exist_ok=True)

        prompt_artifact = (
            "# Prompt\n\n"
            f"{prompt_text}\n\n"
            "# Iteration Context\n\n"
            f"- iteration: {iteration}\n"
            f"- repair_feedback: {repair_feedback}\n"
            f"- input_payload: {json.dumps(input_payload, ensure_ascii=False, sort_keys=True, default=str)}\n"
        )
        (iteration_dir / "prompt.md").write_text(prompt_artifact, encoding="utf-8")

        output = generate_fn(prompt_text, dict(input_payload), list(repair_feedback), iteration)
        final_output = output
        _serialize_json(iteration_dir / "output.json", output)

        checks: list[dict[str, Any]] = []
        all_errors: list[str] = []
        for name, validator in validators.items():
            if not callable(validator):
                normalized = {
                    "name": name,
                    "passed": False,
                    "errors": [f"{name}: validador no callable"],
                }
            else:
                try:
                    raw_result = validator(output, dict(input_payload))
                except Exception as exc:  # pragma: no cover
                    raw_result = {
                        "passed": False,
                        "errors": [f"{type(exc).__name__}: {exc}"],
                    }
                normalized = _normalize_validator_result(name, raw_result)

            checks.append(normalized)
            if not normalized.get("passed", False):
                errors = normalized.get("errors", [])
                if not isinstance(errors, list):
                    errors = [str(errors)]
                all_errors.extend(str(err) for err in errors)

        validation_passed = len(all_errors) == 0
        validation_payload = {
            "validation_passed": validation_passed,
            "checks": checks,
            "repair_action": None if validation_passed else "Reintentar corrigiendo errores de validación",
        }
        _serialize_json(iteration_dir / "validation.json", validation_payload)

        if not validation_passed:
            (iteration_dir / "fix.diff").write_text(
                "\n".join(f"- {err}" for err in all_errors) + "\n",
                encoding="utf-8",
            )

        prompt_hash = _sha256_text(prompt_artifact)
        output_hash = _sha256_text(_stable_json(output))
        status = "OK" if validation_passed else ("REPAIR" if iteration < max_iter else "ERROR")
        manifest_record = {
            "run_id": run_id,
            "node_id": node_id,
            "iteration": iteration,
            "status": status,
            "prompt_hash": prompt_hash,
            "output_hash": output_hash,
            "validation_passed": validation_passed,
            "validation_errors": all_errors,
            "timestamp_utc": _utc_timestamp_iso(),
        }
        _append_jsonl(manifest_path, manifest_record)

        last_validation = validation_payload
        if validation_passed:
            return AlphaLoopResult(
                status="OK",
                run_id=run_id,
                node_id=node_id,
                iterations=iteration,
                final_output=final_output,
                last_validation=last_validation,
                artifacts_dir=str(node_dir),
            )

        repair_feedback = list(all_errors)

    return AlphaLoopResult(
        status="ERROR",
        run_id=run_id,
        node_id=node_id,
        iterations=max_iter,
        final_output=final_output,
        last_validation=last_validation,
        artifacts_dir=str(node_dir),
    )


def alpha_loop_result_to_dict(result: AlphaLoopResult) -> dict[str, Any]:
    """Serializa AlphaLoopResult como diccionario JSON-friendly."""
    return asdict(result)
