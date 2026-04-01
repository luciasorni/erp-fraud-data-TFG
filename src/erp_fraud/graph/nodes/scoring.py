"""Nodo scoring y validador de scoring."""

from __future__ import annotations

# ruff: noqa: F401,F403,F405,F821

from . import _legacy as _legacy

globals().update(vars(_legacy))

def scoring_node(state: GraphState) -> GraphState:
    """Scoring por entidad/transacción + tipología de fraude (RF14-09)."""
    metadata = state.run_metadata if isinstance(state.run_metadata, dict) else {}
    _record_graph_node_model_config(
        node_id="scoring",
        metadata=metadata,
        default_model_used="scoring-stub-v2",
    )
    findings = [row for row in state.findings if isinstance(row, dict)]
    weights_config_path = _resolve_project_path(
        str(metadata.get("weights_config", DEFAULT_WEIGHTS_CONFIG)).strip() or DEFAULT_WEIGHTS_CONFIG
    )
    models_config_path = _resolve_project_path(
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
        _record_graph_node_model_config(
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
        metadata["scoring_prompt_hash"] = str(scoring_prompt_info.get("hash", "")).strip() or _sha256_text(
            scoring_prompt_text
        )
        metadata["scoring_score_hash"] = _sha256_text(_stable_json(state.scores[0]))
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
            resolved_model_used = str(resolved_model.get("model_used", "")).strip() or "scoring-stub-v2"
            metadata["scoring_model_profile"] = str(resolved_model.get("profile", "")).strip()
            metadata["scoring_model_temperature"] = float(resolved_model.get("temperature", 0.0) or 0.0)
            metadata["scoring_model_max_tokens"] = int(resolved_model.get("max_tokens", 0) or 0)
            metadata["scoring_models_config"] = models_config_path
        except Exception:
            resolved_model_used = "scoring-stub-v2"
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
    ) -> dict[str, Any]:
        corrected = dict(payload)
        probs_raw = corrected.get("fraud_type_probs", [])
        probs = [dict(row) for row in probs_raw if isinstance(row, dict)]
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
            repaired = _autocorrect_score_payload(base, findings_payload=[row for row in findings_payload if isinstance(row, dict)])
            return [repaired]

        return [base]

    state.scores = _run_alpha_loop_for_node(
        state=state,
        node_id="scoring",
        prompt_text=scoring_prompt_text,
        input_payload={
            "hypotheses": [row for row in state.hypotheses if isinstance(row, dict)],
            "findings_count": len(findings),
            "findings": findings,
            "acfe_snippets": acfe_snippets,
            "top_k": top_k,
        },
        generate_fn=_generate_scores,
        validators={
            "scores_schema": _validate_scores_output,
            "scores_probabilities": _validate_scoring_evidence_and_probability_sum,
        },
        max_iter=2,
    )
    metadata["scoring_status"] = "OK"
    metadata["scoring_entities"] = len(ranking_rows)
    metadata["scoring_top_k"] = top_k
    metadata["scoring_fraud_types"] = len(fraud_type_probs)
    metadata["scoring_model_used"] = str(base_score_schema.get("model_used", "")).strip()
    _record_graph_node_model_config(
        node_id="scoring",
        metadata=metadata,
        default_model_used=str(base_score_schema.get("model_used", "")).strip() or "scoring-stub-v2",
        overrides={
            "mode": "stub",
            "model_used": str(base_score_schema.get("model_used", "")).strip() or "scoring-stub-v2",
            "temperature": float(metadata.get("scoring_model_temperature", 0.0) or 0.0),
            "max_tokens": int(metadata.get("scoring_model_max_tokens", 0) or 0),
            "profile": str(metadata.get("scoring_model_profile", "")).strip(),
        },
    )
    metadata["scoring_prompt_hash"] = str(scoring_prompt_info.get("hash", "")).strip() or _sha256_text(
        scoring_prompt_text
    )
    metadata["scoring_score_hash"] = _sha256_text(_stable_json(state.scores[0] if state.scores else {}))

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
    ls = _langsmith_snapshot()
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
            "score_compare_hash": _sha256_text(_stable_json(score_compare_payload)),
            "langsmith": ls,
        }
    elif not (bool(ls.get("tracing_enabled")) and bool(ls.get("api_key_present")) and str(ls.get("project", "")).strip()):
        metadata["scoring_experiment"] = {
            "status": "SKIPPED",
            "reason": "langsmith_not_configured",
            "platform": "langsmith",
            "run_id": str(state.run_id),
            "score_compare_hash": _sha256_text(_stable_json(score_compare_payload)),
            "langsmith": ls,
        }
    else:
        metadata["scoring_experiment"] = {
            "status": "READY",
            "reason": "",
            "platform": "langsmith",
            "run_id": str(state.run_id),
            "score_compare_hash": _sha256_text(_stable_json(score_compare_payload)),
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
