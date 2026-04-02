"""Nodo scoring y validador de scoring."""

from __future__ import annotations

from typing import Any

from ...catalog import (
    ScoringAgent,
    aggregate_findings_by_entity,
    load_models_config,
    resolve_scoring_model,
)
from ...catalog.scoring import load_weights_config, resolve_ranking_top_k
from ...config import DEFAULT_WEIGHTS_CONFIG
from .common import langsmith_snapshot, resolve_project_path
from ..state import GraphState
from .alpha_runtime import (
    load_node_prompt,
    record_graph_node_model_config,
    run_alpha_loop_for_node,
    sha256_text,
    stable_json,
)
from .common import annotate_node_llm_mode
from .validators import validate_scores_output
from ..llm_runtime import call_openai_json, resolve_node_runtime_target

# Compat tests: permitir monkeypatch del nombre legacy.
_run_alpha_loop_for_node = run_alpha_loop_for_node

def scoring_node(state: GraphState) -> GraphState:
    """Scoring por entidad/transacción + tipología de fraude (RF14-09)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    llm_mode = annotate_node_llm_mode(metadata=metadata, node_id="scoring")
    runtime_target = resolve_node_runtime_target(
        node_id="scoring",
        metadata=metadata,
        default_model_used="scoring-deterministic-v2",
    )
    record_graph_node_model_config(
        node_id="scoring",
        metadata=metadata,
        default_model_used="scoring-deterministic-v2",
        overrides={
            "mode_effective": str(runtime_target.get("mode_effective", "stub_runtime")),
            "llm_mode": llm_mode,
            "real_mode_requested": llm_mode == "real",
            "provider": str(runtime_target.get("provider", "")).strip(),
            "model_used": str(runtime_target.get("model_used", "")).strip() or "scoring-deterministic-v2",
        },
    )
    runtime_by_node = metadata.setdefault("llm_runtime_by_node", {})
    if not isinstance(runtime_by_node, dict):
        runtime_by_node = {}
        metadata["llm_runtime_by_node"] = runtime_by_node
    findings = [row for row in state.findings if isinstance(row, dict)]
    weights_config_path = resolve_project_path(
        str(metadata.get("weights_config", DEFAULT_WEIGHTS_CONFIG)).strip() or DEFAULT_WEIGHTS_CONFIG
    )
    models_config_path = resolve_project_path(
        str(metadata.get("models_config", "config/models.yaml")).strip() or "config/models.yaml"
    )
    scoring_model_profile = str(metadata.get("scoring_model_profile", "")).strip()
    top_k_override = metadata.get("scoring_top_k")
    simulate_invalid_once = bool(metadata.get("scoring_simulate_invalid_once", False))
    scoring_compare_profiles_raw = metadata.get("scoring_compare_profiles", [])
    if isinstance(scoring_compare_profiles_raw, str):
        scoring_compare_profiles = [
            item.strip() for item in scoring_compare_profiles_raw.split(",") if item.strip()
        ]
    elif isinstance(scoring_compare_profiles_raw, list):
        scoring_compare_profiles = [str(item).strip() for item in scoring_compare_profiles_raw if str(item).strip()]
    else:
        scoring_compare_profiles = []
    scoring_prompt_info = load_node_prompt(
        node_id="scoring",
        fallback_text=(
            "Calcula score por tipología de fraude usando hypotheses + findings + acfe_snippets "
            "y devuelve ScoreSchema válido."
        ),
        registry_path=metadata.get("prompt_registry_path"),
    )
    scoring_prompt_text = str(scoring_prompt_info.get("text", ""))
    metadata["scoring_prompt_path"] = str(scoring_prompt_info.get("path", "")).strip()
    metadata["scoring_prompt_version"] = str(scoring_prompt_info.get("version", "")).strip()
    metadata["scoring_prompt_hash"] = str(scoring_prompt_info.get("hash", "")).strip()
    metadata["scoring_prompt_status"] = str(scoring_prompt_info.get("status", "")).strip()

    if not findings:
        state.ranking = []
        state.fraud_type_predicho = []
        empty_score = ScoringAgent(model_used="scoring-node-no-findings").parse_output(
            ScoringAgent(model_used="scoring-node-no-findings").generate(
                hypotheses=[row for row in state.hypotheses if isinstance(row, dict)],
                findings=[],
                acfe_snippets=[],
            )
        )
        state.scores = [
            {
                **empty_score,
                "ranking": [],
                "fraud_type_distribution": {},
                "summary": {
                    "entities_scored": 0,
                    "findings_total": 0,
                    "top_k": int(top_k_override) if isinstance(top_k_override, int) and top_k_override > 0 else 0,
                },
                "method": "llm_score_schema",
                "source": "scoring_node",
            }
        ]
        metadata["scoring_status"] = "NO_FINDINGS"
        metadata["scoring_entities"] = 0
        metadata["scoring_model_used"] = str(empty_score.get("model_used", "")).strip()
        record_graph_node_model_config(
            node_id="scoring",
            metadata=metadata,
            default_model_used=str(empty_score.get("model_used", "")).strip() or "scoring-node-no-findings",
            overrides={
                "mode": "stub",
                "model_used": str(empty_score.get("model_used", "")).strip() or "scoring-node-no-findings",
                "temperature": 0.0,
                "max_tokens": 0,
                "profile": str(scoring_model_profile).strip(),
            },
        )
        metadata["scoring_prompt_hash"] = str(scoring_prompt_info.get("hash", "")).strip() or sha256_text(
            scoring_prompt_text
        )
        metadata["scoring_score_hash"] = sha256_text(stable_json(state.scores[0]))
        return state

    weights_cfg = load_weights_config(weights_config_path)
    if isinstance(top_k_override, int) and top_k_override > 0:
        top_k = int(top_k_override)
    else:
        top_k = resolve_ranking_top_k(weights_config=weights_cfg, default_top_k=20)

    ranking_rows = aggregate_findings_by_entity(
        test_results=findings,
        weights_config=weights_cfg,
    )
    top_rows = ranking_rows[:top_k]

    fraud_type_distribution: dict[str, int] = {}
    for row in top_rows:
        if not isinstance(row, dict):
            continue
        fraud_types = row.get("fraud_types", [])
        if not isinstance(fraud_types, list):
            continue
        for fraud_type in fraud_types:
            key = str(fraud_type).strip()
            if not key:
                continue
            fraud_type_distribution[key] = fraud_type_distribution.get(key, 0) + 1

    findings_by_fraud_type: dict[str, dict[str, Any]] = {}
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        fraud_type = str(finding.get("fraud_type", "")).strip()
        if not fraud_type:
            continue
        entry = findings_by_fraud_type.setdefault(
            fraud_type,
            {
                "finding_count_total": 0,
                "test_ids": set(),
                "hypothesis_ids": set(),
                "acfe_chunks": set(),
            },
        )
        entry["finding_count_total"] += int(finding.get("finding_count", 0) or 0)
        test_id = str(finding.get("test_id", "")).strip()
        if test_id:
            entry["test_ids"].add(test_id)

    selected_tests = [row for row in state.selected_tests if isinstance(row, dict)]
    for row in selected_tests:
        test_id = str(row.get("test_id", "")).strip()
        hypothesis_id = str(row.get("hypothesis_id", "")).strip()
        if not test_id:
            continue
        for fraud_type, entry in findings_by_fraud_type.items():
            if test_id in entry["test_ids"] and hypothesis_id:
                entry["hypothesis_ids"].add(hypothesis_id)

    for explanation in state.explanations:
        if not isinstance(explanation, dict):
            continue
        fraud_type = str(explanation.get("fraud_type", "")).strip()
        if fraud_type not in findings_by_fraud_type:
            continue
        acfe_reference = explanation.get("acfe_reference", {})
        if not isinstance(acfe_reference, dict):
            continue
        hits = acfe_reference.get("hits", [])
        if not isinstance(hits, list):
            continue
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            chunk_id = str(hit.get("chunk_id", "")).strip()
            if chunk_id:
                findings_by_fraud_type[fraud_type]["acfe_chunks"].add(chunk_id)

    acfe_snippets: list[dict[str, Any]] = []
    for fraud_type in sorted(findings_by_fraud_type.keys()):
        for chunk_id in sorted(findings_by_fraud_type[fraud_type]["acfe_chunks"]):
            acfe_snippets.append({"fraud_type": fraud_type, "chunk_id": chunk_id})

    resolved_model_used = str(metadata.get("scoring_model", "")).strip()
    if not resolved_model_used:
        try:
            models_cfg = load_models_config(models_config_path)
            resolved_model = resolve_scoring_model(models_config=models_cfg, profile=scoring_model_profile)
            resolved_model_used = str(resolved_model.get("model_used", "")).strip() or "scoring-deterministic-v2"
            metadata["scoring_model_profile"] = str(resolved_model.get("profile", "")).strip()
            metadata["scoring_model_temperature"] = float(resolved_model.get("temperature", 0.0) or 0.0)
            metadata["scoring_model_max_tokens"] = int(resolved_model.get("max_tokens", 0) or 0)
            metadata["scoring_models_config"] = models_config_path
        except Exception:
            resolved_model_used = "scoring-deterministic-v2"
    scoring_agent = ScoringAgent(model_used=resolved_model_used)
    base_score_schema = scoring_agent.parse_output(
        scoring_agent.generate(
            hypotheses=[row for row in state.hypotheses if isinstance(row, dict)],
            findings=findings,
            acfe_snippets=acfe_snippets,
        )
    )
    fraud_type_probs: list[dict[str, Any]] = []
    for row in base_score_schema.get("fraud_type_probs", []):
        if not isinstance(row, dict):
            continue
        fraud_type = str(row.get("fraud_type", "")).strip()
        entry = findings_by_fraud_type.get(fraud_type, {})
        enriched = dict(row)
        enriched["evidence_summary"] = (
            f"support={int(entry.get('finding_count_total', 0) or 0)}; "
            f"tests={sorted(entry.get('test_ids', set()))}; "
            f"hypotheses={sorted(entry.get('hypothesis_ids', set()))}"
        )
        enriched["source_hypothesis_ids"] = sorted(entry.get("hypothesis_ids", set()))
        enriched["acfe_chunk_ids"] = sorted(entry.get("acfe_chunks", set()))
        fraud_type_probs.append(enriched)
    base_score_schema["fraud_type_probs"] = fraud_type_probs
    state.fraud_type_predicho = [
        {"fraud_type": row["fraud_type"], "prob": row["probability"]}
        for row in fraud_type_probs
        if isinstance(row, dict)
    ]
    state.ranking = [dict(row) for row in top_rows if isinstance(row, dict)]

    scores_payload = [
        {
            **base_score_schema,
            "ranking": top_rows,
            "fraud_type_distribution": dict(sorted(fraud_type_distribution.items(), key=lambda item: item[0])),
            "summary": {
                "entities_scored": len(ranking_rows),
                "entities_returned": len(top_rows),
                "findings_total": sum(int(row.get("finding_count", 0) or 0) for row in findings),
                "top_k": top_k,
                "weights_config": weights_config_path,
                "fraud_types_scored": len(fraud_type_probs),
            },
            "method": "llm_score_schema",
            "source": "scoring_node",
        }
    ]

    def _autocorrect_score_payload(
        payload: dict[str, Any],
        *,
        findings_payload: list[dict[str, Any]],
        hypotheses_payload: list[dict[str, Any]],
    ) -> dict[str, Any]:
        corrected = dict(payload)
        probs_raw = corrected.get("fraud_type_probs", [])
        probs_in = [dict(row) for row in probs_raw if isinstance(row, dict)]

        allowed_fraud_types: set[str] = set()
        findings_test_ids_by_fraud_type: dict[str, set[str]] = {}
        finding_counts_by_fraud_type: dict[str, int] = {}

        for row in findings_payload:
            if not isinstance(row, dict):
                continue
            fraud_type = str(row.get("fraud_type", "")).strip()
            test_id = str(row.get("test_id", "")).strip()
            if not fraud_type:
                continue
            allowed_fraud_types.add(fraud_type)
            finding_counts_by_fraud_type[fraud_type] = finding_counts_by_fraud_type.get(fraud_type, 0) + int(
                row.get("finding_count", 0) or 0
            )
            if test_id:
                findings_test_ids_by_fraud_type.setdefault(fraud_type, set()).add(test_id)

        for row in hypotheses_payload:
            if not isinstance(row, dict):
                continue
            fraud_type = str(row.get("fraud_type", "")).strip()
            if fraud_type:
                allowed_fraud_types.add(fraud_type)

        fallback_fraud_type = ""
        if finding_counts_by_fraud_type:
            fallback_fraud_type = max(
                finding_counts_by_fraud_type.items(),
                key=lambda item: (int(item[1]), str(item[0])),
            )[0]
        if not fallback_fraud_type and allowed_fraud_types:
            fallback_fraud_type = sorted(allowed_fraud_types)[0]

        # 1) Normaliza/remepea etiquetas fuera de taxonomía.
        remapped: list[dict[str, Any]] = []
        for row in probs_in:
            fraud_type = str(row.get("fraud_type", "")).strip()
            if allowed_fraud_types and fraud_type not in allowed_fraud_types:
                fraud_type = fallback_fraud_type or fraud_type
            if not fraud_type:
                fraud_type = fallback_fraud_type or "unknown"
            row["fraud_type"] = fraud_type
            remapped.append(row)

        # 2) Fusiona duplicados tras remapeo y repara source_test_ids.
        by_fraud_type: dict[str, dict[str, Any]] = {}
        for row in remapped:
            fraud_type = str(row.get("fraud_type", "")).strip()
            if not fraud_type:
                continue
            prob = max(0.0, float(row.get("probability", 0.0) or 0.0))
            source_test_ids_raw = row.get("source_test_ids", [])
            source_test_ids = (
                [str(item).strip() for item in source_test_ids_raw if str(item).strip()]
                if isinstance(source_test_ids_raw, list)
                else []
            )
            allowed_tests = findings_test_ids_by_fraud_type.get(fraud_type, set())
            source_test_ids = [tid for tid in source_test_ids if tid in allowed_tests] if allowed_tests else source_test_ids
            if not source_test_ids and allowed_tests:
                source_test_ids = sorted(allowed_tests)

            if fraud_type not in by_fraud_type:
                out = dict(row)
                out["probability"] = prob
                out["source_test_ids"] = source_test_ids
                by_fraud_type[fraud_type] = out
            else:
                by_fraud_type[fraud_type]["probability"] = float(by_fraud_type[fraud_type].get("probability", 0.0) or 0.0) + prob
                existing = by_fraud_type[fraud_type].get("source_test_ids", [])
                merged_ids = set(existing if isinstance(existing, list) else [])
                merged_ids.update(source_test_ids)
                by_fraud_type[fraud_type]["source_test_ids"] = sorted(str(item).strip() for item in merged_ids if str(item).strip())

        probs = list(by_fraud_type.values())
        total = sum(max(0.0, float(row.get("probability", 0.0) or 0.0)) for row in probs)
        if probs and total > 0:
            for row in probs:
                row["probability"] = max(0.0, float(row.get("probability", 0.0) or 0.0)) / total
        corrected["fraud_type_probs"] = probs

        known_labels = [str(row.get("fraud_type", "")).strip() for row in probs if str(row.get("fraud_type", "")).strip()]
        final_label = str(corrected.get("final_label", "")).strip()
        if not final_label or final_label not in known_labels:
            winner = max(probs, key=lambda row: float(row.get("probability", 0.0) or 0.0), default={})
            corrected["final_label"] = str(winner.get("fraud_type", "")).strip() or "unknown"

        all_test_ids = sorted(
            {
                str(row.get("test_id", "")).strip()
                for row in findings_payload
                if isinstance(row, dict) and str(row.get("test_id", "")).strip()
            }
        )
        evidence_summary = str(corrected.get("evidence_summary", "")).strip()
        if all_test_ids and not any(test_id in evidence_summary for test_id in all_test_ids):
            corrected["evidence_summary"] = f"Evidence from tests: {', '.join(all_test_ids)}"

        try:
            corrected["confidence"] = max(0.0, min(1.0, float(corrected.get("confidence", 0.0) or 0.0)))
        except (TypeError, ValueError):
            corrected["confidence"] = 0.0
        return corrected

    def _generate_scores(
        _prompt: str,
        input_payload: dict[str, Any],
        repair_feedback: list[str],
        iteration: int,
    ) -> list[dict[str, Any]]:
        base = dict(scores_payload[0]) if scores_payload and isinstance(scores_payload[0], dict) else {}
        if bool(runtime_target.get("enabled", False)):
            llm_output, llm_meta = call_openai_json(
                model_used=str(runtime_target.get("model_used", "")).strip() or resolved_model_used,
                temperature=float(runtime_target.get("temperature", 0.0) or 0.0),
                max_tokens=int(runtime_target.get("max_tokens", 0) or 0),
                prompt_text=scoring_prompt_text,
                input_payload=input_payload,
                repair_feedback=repair_feedback,
                timeout_s=float(metadata.get("llm_timeout_s", 30.0) or 30.0),
                max_retries=int(metadata.get("llm_max_retries", 1) or 1),
                retry_backoff_s=float(metadata.get("llm_retry_backoff_s", 0.6) or 0.6),
            )
            metadata["scoring_llm_call_status"] = str(llm_meta.get("status", "ERROR")).strip()
            runtime_by_node["scoring"] = {
                "model_used": str(llm_meta.get("model_used", "")).strip()
                or str(runtime_target.get("model_used", "")).strip()
                or resolved_model_used,
                "llm_mode": llm_mode,
                "latency_ms": int(llm_meta.get("latency_ms", 0) or 0),
                "input_tokens": int(llm_meta.get("input_tokens", 0) or 0),
                "output_tokens": int(llm_meta.get("output_tokens", 0) or 0),
                "total_tokens": int(llm_meta.get("total_tokens", 0) or 0),
                "cost_estimated_usd": float(llm_meta.get("cost_estimated_usd", 0.0) or 0.0),
                "retries_done": int(llm_meta.get("retries_done", 0) or 0),
                "fallback_used": bool(llm_meta.get("fallback_used", llm_output is None)),
                "status": str(llm_meta.get("status", "UNKNOWN")).strip(),
            }
            if isinstance(llm_output, dict):
                try:
                    llm_score = scoring_agent.parse_output(llm_output)
                    base.update(llm_score)
                except Exception:
                    pass
        else:
            metadata["scoring_llm_call_status"] = "SKIPPED"
            runtime_by_node["scoring"] = {
                "model_used": str(runtime_target.get("model_used", "")).strip() or resolved_model_used,
                "llm_mode": llm_mode,
                "latency_ms": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "cost_estimated_usd": 0.0,
                "retries_done": 0,
                "fallback_used": True,
                "status": "STUB_SCORING",
            }
        if iteration == 1 and not repair_feedback and simulate_invalid_once and base:
            # Fuerza un primer intento inválido para probar la ruta de autocorrección.
            bad = dict(base)
            bad["final_label"] = "invalid_label"
            bad["evidence_summary"] = "No references"
            bad_probs = [dict(row) for row in bad.get("fraud_type_probs", []) if isinstance(row, dict)]
            if bad_probs:
                for row in bad_probs:
                    row["probability"] = float(row.get("probability", 0.0) or 0.0) * 1.1
                bad["fraud_type_probs"] = bad_probs
            return [bad]

        if repair_feedback and base:
            findings_payload = input_payload.get("findings", [])
            if not isinstance(findings_payload, list):
                findings_payload = []
            hypotheses_payload = input_payload.get("hypotheses", [])
            if not isinstance(hypotheses_payload, list):
                hypotheses_payload = []
            repaired = _autocorrect_score_payload(
                base,
                findings_payload=[row for row in findings_payload if isinstance(row, dict)],
                hypotheses_payload=[row for row in hypotheses_payload if isinstance(row, dict)],
            )
            return [repaired]

        return [base]

    scoring_input_payload = {
        "hypotheses": [row for row in state.hypotheses if isinstance(row, dict)],
        "findings_count": len(findings),
        "findings": findings,
        "acfe_snippets": acfe_snippets,
        "top_k": top_k,
    }
    try:
        state.scores = _run_alpha_loop_for_node(
            state=state,
            node_id="scoring",
            prompt_text=scoring_prompt_text,
            input_payload=scoring_input_payload,
            generate_fn=_generate_scores,
            validators={
                "scores_schema": validate_scores_output,
                "scores_probabilities": _validate_scoring_evidence_and_probability_sum,
            },
            max_iter=2,
        )
    except Exception as exc:
        fallback_payload = dict(scores_payload[0]) if scores_payload and isinstance(scores_payload[0], dict) else {}
        state.scores = [fallback_payload] if fallback_payload else []
        metadata["scoring_fallback_used"] = True
        metadata["scoring_fallback_reason"] = f"{type(exc).__name__}: {exc}"
        if isinstance(runtime_by_node, dict):
            row = runtime_by_node.get("scoring", {})
            if not isinstance(row, dict):
                row = {}
            row["fallback_used"] = True
            row["status"] = row.get("status") or "FALLBACK_AFTER_VALIDATION_ERROR"
            runtime_by_node["scoring"] = row
    metadata["scoring_status"] = "OK"
    metadata["scoring_entities"] = len(ranking_rows)
    metadata["scoring_top_k"] = top_k
    metadata["scoring_fraud_types"] = len(fraud_type_probs)
    metadata["scoring_model_used"] = str(base_score_schema.get("model_used", "")).strip()
    record_graph_node_model_config(
        node_id="scoring",
        metadata=metadata,
        default_model_used=str(base_score_schema.get("model_used", "")).strip() or "scoring-deterministic-v2",
        overrides={
            "mode": "real" if bool(runtime_target.get("enabled", False)) else "stub",
            "mode_effective": str(runtime_target.get("mode_effective", "stub_runtime")),
            "provider": str(runtime_target.get("provider", "")).strip(),
            "model_used": str(state.scores[0].get("model_used", "")).strip()
            if state.scores and isinstance(state.scores[0], dict)
            else (str(base_score_schema.get("model_used", "")).strip() or "scoring-deterministic-v2"),
            "temperature": float(metadata.get("scoring_model_temperature", 0.0) or 0.0),
            "max_tokens": int(metadata.get("scoring_model_max_tokens", 0) or 0),
            "profile": str(metadata.get("scoring_model_profile", "")).strip(),
        },
    )
    metadata["scoring_prompt_hash"] = str(scoring_prompt_info.get("hash", "")).strip() or sha256_text(
        scoring_prompt_text
    )
    metadata["scoring_score_hash"] = sha256_text(stable_json(state.scores[0] if state.scores else {}))

    if len(scoring_compare_profiles) >= 2:
        try:
            models_cfg = load_models_config(models_config_path)
            baseline_profile = scoring_compare_profiles[0]
            candidate_profile = scoring_compare_profiles[1]
            baseline_model = resolve_scoring_model(models_config=models_cfg, profile=baseline_profile)
            candidate_model = resolve_scoring_model(models_config=models_cfg, profile=candidate_profile)
            baseline_agent = ScoringAgent(model_used=str(baseline_model.get("model_used", "")).strip())
            candidate_agent = ScoringAgent(model_used=str(candidate_model.get("model_used", "")).strip())
            baseline_score = baseline_agent.parse_output(
                baseline_agent.generate(
                    hypotheses=[row for row in state.hypotheses if isinstance(row, dict)],
                    findings=findings,
                    acfe_snippets=acfe_snippets,
                )
            )
            candidate_score = candidate_agent.parse_output(
                candidate_agent.generate(
                    hypotheses=[row for row in state.hypotheses if isinstance(row, dict)],
                    findings=findings,
                    acfe_snippets=acfe_snippets,
                )
            )
            baseline_probs = {
                str(row.get("fraud_type", "")).strip(): float(row.get("probability", 0.0) or 0.0)
                for row in baseline_score.get("fraud_type_probs", [])
                if isinstance(row, dict) and str(row.get("fraud_type", "")).strip()
            }
            candidate_probs = {
                str(row.get("fraud_type", "")).strip(): float(row.get("probability", 0.0) or 0.0)
                for row in candidate_score.get("fraud_type_probs", [])
                if isinstance(row, dict) and str(row.get("fraud_type", "")).strip()
            }
            fraud_types = sorted(set(baseline_probs.keys()) | set(candidate_probs.keys()))
            deltas = [
                {
                    "fraud_type": fraud_type,
                    "baseline_probability": float(baseline_probs.get(fraud_type, 0.0)),
                    "candidate_probability": float(candidate_probs.get(fraud_type, 0.0)),
                    "delta_probability": float(candidate_probs.get(fraud_type, 0.0))
                    - float(baseline_probs.get(fraud_type, 0.0)),
                }
                for fraud_type in fraud_types
            ]
            score_compare = {
                "version": "1.0.0",
                "baseline_profile": str(baseline_model.get("profile", baseline_profile)).strip(),
                "candidate_profile": str(candidate_model.get("profile", candidate_profile)).strip(),
                "baseline_model_used": str(baseline_score.get("model_used", "")).strip(),
                "candidate_model_used": str(candidate_score.get("model_used", "")).strip(),
                "baseline_final_label": str(baseline_score.get("final_label", "")).strip(),
                "candidate_final_label": str(candidate_score.get("final_label", "")).strip(),
                "baseline_confidence": float(baseline_score.get("confidence", 0.0) or 0.0),
                "candidate_confidence": float(candidate_score.get("confidence", 0.0) or 0.0),
                "confidence_delta": float(candidate_score.get("confidence", 0.0) or 0.0)
                - float(baseline_score.get("confidence", 0.0) or 0.0),
                "final_label_changed": str(baseline_score.get("final_label", "")).strip()
                != str(candidate_score.get("final_label", "")).strip(),
                "deltas_by_fraud_type": deltas,
            }
            metadata["score_compare"] = score_compare
            metadata["scoring_compare_status"] = "OK"
            metadata["scoring_compare_profiles"] = [
                str(baseline_model.get("profile", baseline_profile)).strip(),
                str(candidate_model.get("profile", candidate_profile)).strip(),
            ]
        except Exception as exc:
            metadata["scoring_compare_status"] = f"ERROR: {type(exc).__name__}: {exc}"

    # RF18-09: integración LangSmith opcional/no bloqueante (sin depender de RF14b).
    ls = langsmith_snapshot()
    langsmith_experiments_enabled = bool(metadata.get("enable_langsmith_experiments", False))
    score_compare_payload = metadata.get("score_compare")
    if not isinstance(score_compare_payload, dict) or not score_compare_payload:
        metadata["scoring_experiment"] = {
            "status": "SKIPPED",
            "reason": "missing_score_compare",
            "platform": "langsmith",
            "run_id": str(state.run_id),
            "langsmith": ls,
        }
    elif not langsmith_experiments_enabled:
        metadata["scoring_experiment"] = {
            "status": "SKIPPED",
            "reason": "langsmith_experiments_disabled",
            "platform": "langsmith",
            "run_id": str(state.run_id),
            "score_compare_hash": sha256_text(stable_json(score_compare_payload)),
            "langsmith": ls,
        }
    elif not (bool(ls.get("tracing_enabled")) and bool(ls.get("api_key_present")) and str(ls.get("project", "")).strip()):
        metadata["scoring_experiment"] = {
            "status": "SKIPPED",
            "reason": "langsmith_not_configured",
            "platform": "langsmith",
            "run_id": str(state.run_id),
            "score_compare_hash": sha256_text(stable_json(score_compare_payload)),
            "langsmith": ls,
        }
    else:
        metadata["scoring_experiment"] = {
            "status": "READY",
            "reason": "",
            "platform": "langsmith",
            "run_id": str(state.run_id),
            "score_compare_hash": sha256_text(stable_json(score_compare_payload)),
            "trace_link": str(ls.get("trace_link", "")).strip(),
            "langsmith": ls,
        }
    return state

def _validate_scoring_evidence_and_probability_sum(output: Any, input_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(output, list) or not output:
        return {"passed": False, "errors": ["scores debe ser lista no vacía"]}
    first = output[0]
    if not isinstance(first, dict):
        return {"passed": False, "errors": ["scores[0] debe ser objeto"]}
    fraud_type_probs = first.get("fraud_type_probs", [])
    if not isinstance(fraud_type_probs, list):
        return {"passed": False, "errors": ["scores[0].fraud_type_probs debe ser lista"]}
    if not fraud_type_probs:
        return {"passed": True, "errors": []}

    findings = input_payload.get("findings", [])
    if not isinstance(findings, list):
        findings = []
    hypotheses = input_payload.get("hypotheses", [])
    if not isinstance(hypotheses, list):
        hypotheses = []
    findings_by_fraud_type: dict[str, set[str]] = {}
    all_test_ids: set[str] = set()
    allowed_fraud_types: set[str] = set()
    for row in findings:
        if not isinstance(row, dict):
            continue
        fraud_type = str(row.get("fraud_type", "")).strip()
        test_id = str(row.get("test_id", "")).strip()
        if not fraud_type or not test_id:
            continue
        allowed_fraud_types.add(fraud_type)
        all_test_ids.add(test_id)
        findings_by_fraud_type.setdefault(fraud_type, set()).add(test_id)
    for row in hypotheses:
        if not isinstance(row, dict):
            continue
        fraud_type = str(row.get("fraud_type", "")).strip()
        if fraud_type:
            allowed_fraud_types.add(fraud_type)

    errors: list[str] = []
    total_prob = 0.0
    for idx, row in enumerate(fraud_type_probs):
        if not isinstance(row, dict):
            errors.append(f"fraud_type_probs[{idx}] debe ser objeto")
            continue
        fraud_type = str(row.get("fraud_type", "")).strip()
        prob = float(row.get("probability", 0.0) or 0.0)
        total_prob += prob
        if allowed_fraud_types and fraud_type not in allowed_fraud_types:
            errors.append(f"fraud_type_probs[{idx}].fraud_type fuera de taxonomía permitida: {fraud_type}")
        source_test_ids = row.get("source_test_ids", [])
        if not isinstance(source_test_ids, list):
            errors.append(f"fraud_type_probs[{idx}].source_test_ids debe ser lista")
            continue
        allowed_ids = findings_by_fraud_type.get(fraud_type, set())
        unknown = [
            str(test_id).strip()
            for test_id in source_test_ids
            if str(test_id).strip() and str(test_id).strip() not in allowed_ids
        ]
        if unknown:
            errors.append(
                f"fraud_type_probs[{idx}] referencia source_test_ids no presentes en findings: {unknown}"
            )

    if abs(total_prob - 1.0) > 0.001:
        errors.append(f"fraud_type_probs.probability suma {total_prob:.6f} (esperado ~1.0)")

    final_label = str(first.get("final_label", "")).strip()
    if final_label:
        known_labels = {
            str(row.get("fraud_type", "")).strip()
            for row in fraud_type_probs
            if isinstance(row, dict) and str(row.get("fraud_type", "")).strip()
        }
        if final_label not in known_labels:
            errors.append(f"final_label fuera de fraud_type_probs: {final_label}")
        if allowed_fraud_types and final_label not in allowed_fraud_types:
            errors.append(f"final_label fuera de taxonomía permitida: {final_label}")

    evidence_summary = str(first.get("evidence_summary", "")).strip()
    if all_test_ids:
        references_known_test = any(test_id in evidence_summary for test_id in sorted(all_test_ids))
        if not references_known_test:
            errors.append("evidence_summary no referencia test_id real de findings")
    return {"passed": len(errors) == 0, "errors": errors}
