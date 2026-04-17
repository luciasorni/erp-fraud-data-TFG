"""RF16: persistencia lógica y comparación de runs (P2P/O2C) con recomendaciones."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunSnapshot:
    run_id: str
    run_dir: Path | None
    dataset_id: str
    dataset_hash: str
    process_family: str
    llm_mode: str
    graph_status: str
    overall_status: str
    selected_test_ids: list[str]
    selected_tests_count: int
    findings_total: int
    tests_with_findings: list[str]
    fraud_types_with_findings: dict[str, int]
    hypotheses_count: int
    final_label: str
    confidence: float
    langsmith_trace_link: str
    generated_at_utc: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_score_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, list) and raw:
        return _safe_dict(raw[0])
    return _safe_dict(raw)


def discover_run_ids(*, base_dir: str | Path = "run_results") -> list[str]:
    root = Path(base_dir)
    if not root.exists():
        return []
    out: list[tuple[int, str]] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if (child / "graph").exists() or (child / "report.json").exists() or (child / "run_metadata.json").exists():
            out.append((child.stat().st_mtime_ns, child.name))
    out.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [name for _mtime_ns, name in out]


def load_run_snapshot(*, run_id: str, base_dir: str | Path = "run_results") -> RunSnapshot:
    rid = str(run_id).strip()
    if not rid:
        raise ValueError("run_id debe ser string no vacío")
    run_dir = Path(base_dir) / rid
    if not run_dir.exists() or not run_dir.is_dir():
        raise FileNotFoundError(f"No existe run_dir: {run_dir}")

    graph_dir = run_dir / "graph"
    selected_tests = _safe_list(_load_json(graph_dir / "selected_tests.json"))
    findings = _safe_list(_load_json(graph_dir / "findings.json"))
    hypotheses = _safe_list(_load_json(graph_dir / "hypotheses.json"))
    scores = _normalize_score_payload(_load_json(graph_dir / "scores.json"))
    graph_state = _safe_dict(_load_json(graph_dir / "graph_state.json"))
    graph_meta = _safe_dict(graph_state.get("run_metadata", {}))
    run_metadata_payload = _safe_dict(_load_json(run_dir / "run_metadata.json"))
    api_request_payload = _safe_dict(_load_json(run_dir / "api_request.json"))

    report_payload = _safe_dict(_load_json(run_dir / "report.json"))
    report_summary = _safe_dict(report_payload.get("summary", {}))
    report_metadata = _safe_dict(report_payload.get("metadata", {}))
    report_metadata_extra = _safe_dict(report_metadata.get("metadata_extra", {}))
    selected_test_ids: list[str] = []
    for row in selected_tests:
        item = _safe_dict(row)
        test_id = str(item.get("test_id", "")).strip()
        if test_id and test_id not in selected_test_ids:
            selected_test_ids.append(test_id)

    tests_with_findings: list[str] = []
    fraud_types_with_findings: dict[str, int] = {}
    findings_total = 0
    for row in findings:
        item = _safe_dict(row)
        test_id = str(item.get("test_id", "")).strip()
        fraud_type = str(item.get("fraud_type", "")).strip()
        finding_count = int(item.get("finding_count", 0) or 0)
        findings_total += finding_count
        if finding_count > 0 and test_id and test_id not in tests_with_findings:
            tests_with_findings.append(test_id)
        if finding_count > 0 and fraud_type:
            fraud_types_with_findings[fraud_type] = fraud_types_with_findings.get(fraud_type, 0) + finding_count

    if findings_total <= 0:
        findings_total = int(report_summary.get("findings_total", 0) or 0)

    process_family = (
        str(graph_meta.get("process_family", "")).strip()
        or str(run_metadata_payload.get("process_family", "")).strip()
        or str(report_metadata_extra.get("process_family", "")).strip()
        or "p2p"
    )
    dataset_id = (
        str(api_request_payload.get("dataset_id", "")).strip()
        or str(run_metadata_payload.get("dataset_id", "")).strip()
        or str(report_metadata_extra.get("dataset_id", "")).strip()
    )
    dataset_hash = (
        str(graph_meta.get("dataset_hash", "")).strip()
        or str(run_metadata_payload.get("dataset_hash", "")).strip()
        or str(report_metadata_extra.get("dataset_hash", "")).strip()
    )
    llm_mode = (
        str(graph_meta.get("llm_mode", "")).strip()
        or str(run_metadata_payload.get("llm_mode", "")).strip()
        or str(report_metadata_extra.get("llm_mode", "")).strip()
    )
    graph_status = str(graph_meta.get("graph_status", "")).strip()
    overall_status = str(report_summary.get("overall_status", "")).strip() or graph_status
    final_label = str(scores.get("final_label", "")).strip()
    confidence = float(scores.get("confidence", 0.0) or 0.0)
    langsmith_trace_link = str(graph_meta.get("langsmith_trace_link", "")).strip()
    if not langsmith_trace_link:
        langsmith_trace_link = str(_safe_dict(graph_meta.get("langsmith_runs", {})).get("trace_link", "")).strip()

    generated_at_utc = str(graph_meta.get("updated_at_utc", "")).strip()
    if not generated_at_utc:
        generated_at_utc = str(report_payload.get("generated_at_utc", "")).strip()
    if not generated_at_utc:
        generated_at_utc = _utc_now_iso()

    return RunSnapshot(
        run_id=rid,
        run_dir=run_dir,
        dataset_id=dataset_id,
        dataset_hash=dataset_hash,
        process_family=process_family,
        llm_mode=llm_mode,
        graph_status=graph_status,
        overall_status=overall_status,
        selected_test_ids=selected_test_ids,
        selected_tests_count=len(selected_test_ids),
        findings_total=findings_total,
        tests_with_findings=sorted(tests_with_findings),
        fraud_types_with_findings=dict(sorted(fraud_types_with_findings.items(), key=lambda item: item[0])),
        hypotheses_count=len([row for row in hypotheses if isinstance(row, dict)]),
        final_label=final_label,
        confidence=confidence,
        langsmith_trace_link=langsmith_trace_link,
        generated_at_utc=generated_at_utc,
    )


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return float(len(a & b) / len(a | b))


def _build_recommendations(*, snapshots: list[RunSnapshot]) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    if not snapshots:
        return recs

    families = sorted({row.process_family for row in snapshots if row.process_family})

    for snap in snapshots:
        zero_finding_selected = sorted(set(snap.selected_test_ids) - set(snap.tests_with_findings))
        if zero_finding_selected:
            recs.append(
                {
                    "id": f"REC-{snap.run_id}-001",
                    "severity": "medium",
                    "title": "Revisar tests seleccionados sin hallazgos",
                    "run_id": snap.run_id,
                    "rationale": (
                        f"El run {snap.run_id} seleccionó {len(zero_finding_selected)} tests sin hallazgos. "
                        "Puede deberse a umbrales altos o baja cobertura de hipótesis en ese dataset."
                    ),
                    "actions": [
                        "Revisar umbrales de los tests sin hallazgos frente a distribución real del dataset.",
                        "Añadir caso de auditoría manual para una muestra de 10 entidades de alto riesgo aunque no haya findings.",
                        "Comparar con run histórico equivalente para confirmar estabilidad de señal.",
                    ],
                }
            )

    if len(families) >= 2:
        by_family_fraud_types: dict[str, set[str]] = {}
        for snap in snapshots:
            by_family_fraud_types.setdefault(snap.process_family, set()).update(snap.fraud_types_with_findings.keys())

        common: set[str] | None = None
        for values in by_family_fraud_types.values():
            common = set(values) if common is None else (common & set(values))
        common = common or set()
        if common:
            recs.append(
                {
                    "id": "REC-CROSS-001",
                    "severity": "high",
                    "title": "Concurrencia de tipologías entre procesos",
                    "run_id": "cross_process",
                    "rationale": (
                        "Se detectaron tipologías comunes entre P2P y O2C: "
                        + ", ".join(sorted(common))
                        + "."
                    ),
                    "actions": [
                        "Priorizar auditoría transversal por proveedor/cliente para entidades vinculadas a esas tipologías.",
                        "Añadir procedimiento de reconciliación interproceso (pedido-entrega-factura-cobro/pago).",
                        "Programar re-ejecución semanal comparativa para medir persistencia de concurrencia.",
                    ],
                }
            )
        else:
            recs.append(
                {
                    "id": "REC-CROSS-002",
                    "severity": "low",
                    "title": "Sin concurrencia directa de tipologías entre procesos",
                    "run_id": "cross_process",
                    "rationale": "No se observan tipologías comunes con hallazgos entre familias de proceso en esta comparación.",
                    "actions": [
                        "Mantener monitorización separada por proceso.",
                        "Ampliar catálogo de tests en el proceso con menor señal para mejorar cobertura.",
                    ],
                }
            )
    else:
        recs.append(
            {
                "id": "REC-SINGLE-001",
                "severity": "low",
                "title": "Comparación interproceso pendiente",
                "run_id": snapshots[0].run_id,
                "rationale": "Solo hay una familia de proceso en el análisis; no se puede inferir concurrencia P2P-O2C.",
                "actions": [
                    "Ejecutar al menos un run de la otra familia de proceso y repetir compare-runs.",
                    "Usar el mismo dataset hash lógico cuando sea posible para comparación más consistente.",
                ],
            }
        )

    return recs


def _build_comparison_sections(*, snapshots: list[RunSnapshot]) -> list[dict[str, Any]]:
    if not snapshots:
        return []

    current = snapshots[0]
    historical_peers = [row for row in snapshots[1:] if row.process_family == current.process_family]
    cross_process_peers = [row for row in snapshots[1:] if row.process_family != current.process_family]

    sections: list[dict[str, Any]] = []

    sections.append(
        {
            "id": "intra-run-current",
            "section": "intra_run",
            "status": "comparison",
            "title": "Lectura del run actual",
            "subtitle": f"Run {current.run_id} · {current.process_family.upper()}",
            "summary": (
                f"El run actual seleccionó {current.selected_tests_count} tests, generó {current.findings_total} hallazgos "
                f"y terminó con la etiqueta final {current.final_label or 'sin etiqueta final'} "
                f"y confianza {current.confidence:.2f}."
            ),
            "evidence": [
                f"Tests seleccionados: {', '.join(current.selected_test_ids) or 'ninguno'}.",
                f"Tests con hallazgos: {', '.join(current.tests_with_findings) or 'ninguno'}.",
                f"Tipologías con hallazgos: {', '.join(sorted(current.fraud_types_with_findings.keys())) or 'ninguna'}.",
            ],
            "implication": "Esta lectura resume la señal del run antes de contrastarla con histórico o con otras familias.",
            "attributes": {
                "runs_compared": [current.run_id],
                "dataset_id": current.dataset_id or None,
                "dataset_hash": current.dataset_hash or None,
            },
        }
    )

    if historical_peers:
        common_tests = sorted(
            set(current.selected_test_ids).intersection(*[set(row.selected_test_ids) for row in historical_peers])
        ) if historical_peers else []
        common_types = sorted(
            set(current.fraud_types_with_findings.keys()).intersection(
                *[set(row.fraud_types_with_findings.keys()) for row in historical_peers]
            )
        ) if historical_peers else []
        avg_findings = sum(row.findings_total for row in historical_peers) / max(len(historical_peers), 1)
        sections.append(
            {
                "id": "historical-comparison",
                "section": "historical",
                "status": "comparison",
                "title": "Comparación histórica intra-familia",
                "subtitle": f"{len(historical_peers)} run(s) previo(s) de {current.process_family.upper()}",
                "summary": (
                    f"El run actual se ha contrastado con {len(historical_peers)} runs previos equivalentes de la misma familia. "
                    f"El histórico presenta una media de {avg_findings:.1f} hallazgos."
                ),
                "evidence": [
                    f"Runs históricos: {', '.join(row.run_id for row in historical_peers)}.",
                    f"Tests comunes: {', '.join(common_tests) or 'ninguno'}.",
                    f"Tipologías comunes con hallazgos: {', '.join(common_types) or 'ninguna'}.",
                ],
                "implication": (
                    "Sirve para decidir si la señal actual es estable respecto al histórico o si aparece como una desviación nueva."
                ),
                "recommendation": (
                    "Comparar manualmente el run actual con el último run equivalente cuando haya diferencias relevantes en hallazgos o tipologías."
                ),
                "attributes": {
                    "runs_compared": [current.run_id, *[row.run_id for row in historical_peers]],
                    "same_family": current.process_family,
                },
            }
        )
    else:
        sections.append(
            {
                "id": "historical-comparison-missing",
                "section": "historical",
                "status": "insufficient_context",
                "title": "Comparación histórica intra-familia",
                "subtitle": f"Sin histórico suficiente de {current.process_family.upper()}",
                "summary": (
                    "No hay runs previos equivalentes de la misma familia con contexto suficiente para una comparación histórica útil."
                ),
                "evidence": [
                    f"Run actual: {current.run_id}.",
                ],
                "implication": "La lectura debe apoyarse en la señal del run actual y no en tendencia histórica.",
                "attributes": {"runs_compared": [current.run_id]},
            }
        )

    if cross_process_peers:
        common_types = sorted(
            set(current.fraud_types_with_findings.keys()).intersection(
                *[set(row.fraud_types_with_findings.keys()) for row in cross_process_peers]
            )
        ) if cross_process_peers else []
        common_tests = sorted(
            set(current.selected_test_ids).intersection(*[set(row.selected_test_ids) for row in cross_process_peers])
        ) if cross_process_peers else []
        sections.append(
            {
                "id": "cross-process-comparison",
                "section": "cross_process",
                "status": "comparison",
                "title": "Comparación cross-process",
                "subtitle": "Contraste entre familias de proceso",
                "summary": (
                    f"El run actual se ha contrastado con {len(cross_process_peers)} run(s) de otra familia de proceso "
                    "para identificar concurrencia o divergencia de señal."
                ),
                "evidence": [
                    f"Runs cross-process: {', '.join(row.run_id for row in cross_process_peers)}.",
                    f"Tests comunes: {', '.join(common_tests) or 'ninguno'}.",
                    f"Tipologías comunes con hallazgos: {', '.join(common_types) or 'ninguna'}.",
                ],
                "implication": (
                    "La comparación cross-process ayuda a decidir si la señal parece localizada en un proceso o sugiere patrón transversal."
                ),
                "recommendation": (
                    "Si hay tipologías comunes, revisar entidades relacionadas entre procesos; si no las hay, interpretar la señal como específica del proceso actual."
                ),
                "attributes": {
                    "runs_compared": [current.run_id, *[row.run_id for row in cross_process_peers]],
                    "process_families": sorted({current.process_family, *[row.process_family for row in cross_process_peers]}),
                },
            }
        )
    else:
        sections.append(
            {
                "id": "cross-process-comparison-missing",
                "section": "cross_process",
                "status": "insufficient_context",
                "title": "Comparación cross-process",
                "subtitle": "Sin contraste entre familias",
                "summary": (
                    "No hay runs de otra familia de proceso con contexto suficiente para evaluar concurrencia o divergencia cross-process."
                ),
                "evidence": [
                    f"Run actual: {current.run_id}.",
                ],
                "implication": "No se puede inferir patrón transversal entre P2P y O2C con la información disponible.",
                "attributes": {"runs_compared": [current.run_id]},
            }
        )

    return sections


def compare_run_snapshots(*, snapshots: list[RunSnapshot]) -> dict[str, Any]:
    normalized = [row for row in snapshots if isinstance(row, RunSnapshot)]
    if not normalized:
        raise ValueError("snapshots vacío")

    runs_payload: list[dict[str, Any]] = []
    selected_sets: list[set[str]] = []
    finding_type_sets: list[set[str]] = []
    process_families: dict[str, int] = {}

    for snap in normalized:
        selected = set(snap.selected_test_ids)
        finding_types = set(snap.fraud_types_with_findings.keys())
        selected_sets.append(selected)
        finding_type_sets.append(finding_types)
        process_families[snap.process_family] = process_families.get(snap.process_family, 0) + 1

        runs_payload.append(
            {
                "run_id": snap.run_id,
                "dataset_id": snap.dataset_id,
                "dataset_hash": snap.dataset_hash,
                "process_family": snap.process_family,
                "llm_mode": snap.llm_mode,
                "graph_status": snap.graph_status,
                "overall_status": snap.overall_status,
                "hypotheses_count": snap.hypotheses_count,
                "selected_tests_count": snap.selected_tests_count,
                "selected_test_ids": snap.selected_test_ids,
                "findings_total": snap.findings_total,
                "tests_with_findings": snap.tests_with_findings,
                "fraud_types_with_findings": snap.fraud_types_with_findings,
                "final_label": snap.final_label,
                "confidence": snap.confidence,
                "langsmith_trace_link": snap.langsmith_trace_link,
                "generated_at_utc": snap.generated_at_utc,
            }
        )

    common_selected_tests = sorted(set.intersection(*selected_sets)) if selected_sets else []
    common_fraud_types = sorted(set.intersection(*finding_type_sets)) if finding_type_sets else []

    pairwise: list[dict[str, Any]] = []
    for i in range(len(normalized)):
        for j in range(i + 1, len(normalized)):
            left = normalized[i]
            right = normalized[j]
            left_sel = set(left.selected_test_ids)
            right_sel = set(right.selected_test_ids)
            left_ft = set(left.fraud_types_with_findings.keys())
            right_ft = set(right.fraud_types_with_findings.keys())
            pairwise.append(
                {
                    "left_run_id": left.run_id,
                    "right_run_id": right.run_id,
                    "selected_tests_jaccard": _jaccard(left_sel, right_sel),
                    "fraud_types_jaccard": _jaccard(left_ft, right_ft),
                    "common_selected_tests": sorted(left_sel & right_sel),
                    "common_fraud_types_with_findings": sorted(left_ft & right_ft),
                }
            )

    recommendations = _build_recommendations(snapshots=normalized)
    comparison_sections = _build_comparison_sections(snapshots=normalized)

    return {
        "rf_task": "RF16",
        "generated_at_utc": _utc_now_iso(),
        "runs_count": len(normalized),
        "process_families": dict(sorted(process_families.items(), key=lambda item: item[0])),
        "runs": runs_payload,
        "summary": {
            "current_run_id": normalized[0].run_id,
            "historical_run_ids": [row.run_id for row in normalized[1:] if row.process_family == normalized[0].process_family],
            "cross_process_run_ids": [row.run_id for row in normalized[1:] if row.process_family != normalized[0].process_family],
            "common_selected_tests": common_selected_tests,
            "common_fraud_types_with_findings": common_fraud_types,
            "pairwise_similarity": pairwise,
        },
        "comparison_sections": comparison_sections,
        "recommendations": recommendations,
    }


def compare_runs(*, run_ids: list[str], base_dir: str | Path = "run_results") -> dict[str, Any]:
    if not isinstance(run_ids, list) or not run_ids:
        raise ValueError("run_ids debe ser lista no vacía")
    snapshots = [load_run_snapshot(run_id=rid, base_dir=base_dir) for rid in run_ids]
    return compare_run_snapshots(snapshots=snapshots)


def list_runs(*, base_dir: str | Path = "run_results") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run_id in discover_run_ids(base_dir=base_dir):
        try:
            snap = load_run_snapshot(run_id=run_id, base_dir=base_dir)
        except Exception:
            continue
        rows.append(
            {
                "run_id": snap.run_id,
                "process_family": snap.process_family,
                "llm_mode": snap.llm_mode,
                "graph_status": snap.graph_status,
                "overall_status": snap.overall_status,
                "selected_tests_count": snap.selected_tests_count,
                "findings_total": snap.findings_total,
                "final_label": snap.final_label,
                "confidence": snap.confidence,
                "generated_at_utc": snap.generated_at_utc,
            }
        )
    return rows


def pick_latest_run_ids_by_process_family(
    *,
    base_dir: str | Path = "run_results",
    process_families: tuple[str, ...] = ("p2p", "o2c"),
) -> list[str]:
    wanted = {str(item).strip().lower() for item in process_families if str(item).strip()}
    preferred: dict[str, str] = {}
    fallback: dict[str, str] = {}
    for run_id in discover_run_ids(base_dir=base_dir):
        if len(preferred) == len(wanted):
            break
        try:
            snap = load_run_snapshot(run_id=run_id, base_dir=base_dir)
        except Exception:
            continue
        fam = snap.process_family.lower()
        if fam not in wanted:
            continue
        if fam not in fallback:
            fallback[fam] = run_id
        has_graph_outputs = (snap.run_dir / "graph").exists()
        has_selected_tests = int(snap.selected_tests_count) > 0
        if (has_graph_outputs or has_selected_tests) and fam not in preferred:
            preferred[fam] = run_id

    resolved: dict[str, str] = {}
    for fam in sorted(wanted):
        if fam in preferred:
            resolved[fam] = preferred[fam]
        elif fam in fallback:
            resolved[fam] = fallback[fam]
    return [resolved[fam] for fam in sorted(resolved.keys())]


def build_comparison_markdown(payload: dict[str, Any]) -> str:
    data = payload if isinstance(payload, dict) else {}
    runs = _safe_list(data.get("runs"))
    summary = _safe_dict(data.get("summary"))
    recs = _safe_list(data.get("recommendations"))

    lines = [
        "# RF16 — Second-Level Explainer",
        "",
        "## Resumen",
        "",
        f"- `generated_at_utc`: `{data.get('generated_at_utc', '')}`",
        f"- `runs_count`: `{data.get('runs_count', 0)}`",
        f"- `process_families`: `{data.get('process_families', {})}`",
        "",
        "## Runs analizados",
        "",
        "| run_id | process_family | llm_mode | selected_tests | findings_total | final_label | confidence |",
        "|---|---|---|---:|---:|---|---:|",
    ]
    for row in runs:
        item = _safe_dict(row)
        lines.append(
            "| "
            + f"{item.get('run_id', '')} | {item.get('process_family', '')} | {item.get('llm_mode', '')} | "
            + f"{int(item.get('selected_tests_count', 0) or 0)} | {int(item.get('findings_total', 0) or 0)} | "
            + f"{item.get('final_label', '')} | {float(item.get('confidence', 0.0) or 0.0):.2f} |"
        )

    lines.extend(
        [
            "",
            "## Similitudes",
            "",
            f"- `common_selected_tests`: `{summary.get('common_selected_tests', [])}`",
            f"- `common_fraud_types_with_findings`: `{summary.get('common_fraud_types_with_findings', [])}`",
            "",
            "## Recomendaciones de auditoría",
            "",
        ]
    )
    if recs:
        for idx, row in enumerate(recs, start=1):
            item = _safe_dict(row)
            lines.append(
                f"{idx}. [{item.get('severity', '').upper()}] {item.get('title', '')} — {item.get('rationale', '')}"
            )
            for action in _safe_list(item.get("actions")):
                lines.append(f"   - {action}")
    else:
        lines.append("- Sin recomendaciones.")

    lines.append("")
    return "\n".join(lines)


def write_comparison_outputs(
    *,
    payload: dict[str, Any],
    output_json_path: str | Path,
    output_md_path: str | Path,
) -> tuple[Path, Path]:
    json_path = Path(output_json_path)
    md_path = Path(output_md_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(build_comparison_markdown(payload), encoding="utf-8")
    return json_path, md_path
