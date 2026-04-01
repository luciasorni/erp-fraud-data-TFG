"""RF14b-08: ejecuta experimentos de modelos (planner + scoring) y compara outputs.

Uso rápido:
  python3 scripts/run_rf14b_experiments.py
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.erp_fraud.graph import create_initial_graph_state, run_graph  # noqa: E402

RUN_RESULTS_DIR = PROJECT_ROOT / "run_results"


@dataclass(frozen=True)
class PlannerExperimentResult:
    baseline_run_id: str
    candidate_run_id: str
    baseline_model: str
    candidate_model: str
    baseline_selected_tests: list[str]
    candidate_selected_tests: list[str]
    selected_tests_changed: bool
    baseline_hypothesis_ids: list[str]
    candidate_hypothesis_ids: list[str]
    hypothesis_ids_changed: bool


@dataclass(frozen=True)
class ScoringExperimentResult:
    run_id: str
    baseline_profile: str
    candidate_profile: str
    scoring_compare_status: str
    baseline_model_used: str
    candidate_model_used: str
    baseline_final_label: str
    candidate_final_label: str
    final_label_changed: bool
    confidence_delta: float



def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str)


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _extract_selected_test_ids(state: Any) -> list[str]:
    rows = getattr(state, "selected_tests", [])
    ids = {
        str(row.get("test_id", "")).strip()
        for row in rows
        if isinstance(row, dict) and str(row.get("test_id", "")).strip()
    }
    return sorted(ids)


def _extract_hypothesis_ids(state: Any) -> list[str]:
    rows = getattr(state, "hypotheses", [])
    ids = {
        str(row.get("hypothesis_id", "")).strip()
        for row in rows
        if isinstance(row, dict) and str(row.get("hypothesis_id", "")).strip()
    }
    return sorted(ids)


def _build_models_variants(
    *,
    base_models_config: Path,
    out_dir: Path,
    planner_baseline_model: str,
    planner_candidate_model: str,
) -> tuple[Path, Path]:
    base_cfg = _load_yaml(base_models_config)

    baseline_cfg = copy.deepcopy(base_cfg)
    candidate_cfg = copy.deepcopy(base_cfg)

    for cfg, planner_model in (
        (baseline_cfg, planner_baseline_model),
        (candidate_cfg, planner_candidate_model),
    ):
        graph_nodes = cfg.setdefault("graph_nodes", {})
        if not isinstance(graph_nodes, dict):
            graph_nodes = {}
            cfg["graph_nodes"] = graph_nodes

        hyp = graph_nodes.setdefault("hypothesis_planner", {})
        if not isinstance(hyp, dict):
            hyp = {}
            graph_nodes["hypothesis_planner"] = hyp
        hyp["model_used"] = planner_model

        tplan = graph_nodes.setdefault("test_planner", {})
        if not isinstance(tplan, dict):
            tplan = {}
            graph_nodes["test_planner"] = tplan
        tplan["model_used"] = planner_model

    baseline_path = out_dir / "models_planner_baseline.yaml"
    candidate_path = out_dir / "models_planner_candidate.yaml"
    _write_yaml(baseline_path, baseline_cfg)
    _write_yaml(candidate_path, candidate_cfg)
    return baseline_path, candidate_path


def run_planner_experiment(
    *,
    run_id_prefix: str,
    base_models_config: Path,
    planner_baseline_model: str,
    planner_candidate_model: str,
    catalog_path: str,
    out_dir: Path,
) -> PlannerExperimentResult:
    baseline_cfg, candidate_cfg = _build_models_variants(
        base_models_config=base_models_config,
        out_dir=out_dir,
        planner_baseline_model=planner_baseline_model,
        planner_candidate_model=planner_candidate_model,
    )

    base_metadata = {
        "alphacodium_enabled": False,
        "kb_search_enabled": False,
        "catalog_path": catalog_path,
        "graph_default_retries": 0,
    }

    baseline_run_id = f"{run_id_prefix}-planner-baseline"
    state_base = create_initial_graph_state(run_id=baseline_run_id)
    state_base.run_metadata.update(base_metadata)
    state_base.run_metadata["models_config"] = str(baseline_cfg)
    out_base = run_graph(initial_state=state_base, sequence=("hypothesis_planner", "test_planner"))

    candidate_run_id = f"{run_id_prefix}-planner-candidate"
    state_cand = create_initial_graph_state(run_id=candidate_run_id)
    state_cand.run_metadata.update(base_metadata)
    state_cand.run_metadata["models_config"] = str(candidate_cfg)
    out_cand = run_graph(initial_state=state_cand, sequence=("hypothesis_planner", "test_planner"))

    base_selected = _extract_selected_test_ids(out_base)
    cand_selected = _extract_selected_test_ids(out_cand)
    base_hyp_ids = _extract_hypothesis_ids(out_base)
    cand_hyp_ids = _extract_hypothesis_ids(out_cand)

    return PlannerExperimentResult(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        baseline_model=planner_baseline_model,
        candidate_model=planner_candidate_model,
        baseline_selected_tests=base_selected,
        candidate_selected_tests=cand_selected,
        selected_tests_changed=base_selected != cand_selected,
        baseline_hypothesis_ids=base_hyp_ids,
        candidate_hypothesis_ids=cand_hyp_ids,
        hypothesis_ids_changed=base_hyp_ids != cand_hyp_ids,
    )


def run_scoring_experiment(
    *,
    run_id_prefix: str,
    models_config: Path,
    scoring_baseline_profile: str,
    scoring_candidate_profile: str,
) -> ScoringExperimentResult:
    run_id = f"{run_id_prefix}-scoring-compare"
    state = create_initial_graph_state(run_id=run_id)
    state.run_metadata.update(
        {
            "models_config": str(models_config),
            "scoring_compare_profiles": [scoring_baseline_profile, scoring_candidate_profile],
            "enable_langsmith_experiments": False,
            "alphacodium_enabled": False,
        }
    )

    state.hypotheses = [
        {
            "hypothesis_id": "HYP-EXP-001",
            "title": "Duplicate postings",
            "description": "Potential duplicate payments.",
            "fraud_type": "duplicate_payment",
        },
        {
            "hypothesis_id": "HYP-EXP-002",
            "title": "Unusual amount",
            "description": "Potential amount anomaly.",
            "fraud_type": "amount_anomaly",
        },
    ]
    state.findings = [
        {
            "test_id": "TST-DUPLICATE-POSTINGS",
            "test_version": "1.0.0",
            "fraud_type": "duplicate_payment",
            "status": "OK",
            "finding_count": 2,
            "rows": [
                {
                    "entity_key": "kreditor=V1|belegnummer=D1",
                    "keys": {"kreditor": "V1", "belegnummer": "D1"},
                    "evidence_columns": ["kreditor", "belegnummer", "duplicate_count"],
                    "metrics": {"duplicate_count": 2},
                }
            ],
        },
        {
            "test_id": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
            "test_version": "1.0.0",
            "fraud_type": "amount_anomaly",
            "status": "OK",
            "finding_count": 1,
            "rows": [
                {
                    "entity_key": "kreditor=V2|belegnummer=D2",
                    "keys": {"kreditor": "V2", "belegnummer": "D2"},
                    "evidence_columns": ["kreditor", "z_score"],
                    "metrics": {"z_score": 4.0},
                }
            ],
        },
    ]

    out = run_graph(initial_state=state, sequence=("scoring",))
    metadata = out.run_metadata if isinstance(out.run_metadata, dict) else {}
    compare = metadata.get("score_compare", {}) if isinstance(metadata.get("score_compare"), dict) else {}

    return ScoringExperimentResult(
        run_id=run_id,
        baseline_profile=str(compare.get("baseline_profile", scoring_baseline_profile)),
        candidate_profile=str(compare.get("candidate_profile", scoring_candidate_profile)),
        scoring_compare_status=str(metadata.get("scoring_compare_status", "")),
        baseline_model_used=str(compare.get("baseline_model_used", "")),
        candidate_model_used=str(compare.get("candidate_model_used", "")),
        baseline_final_label=str(compare.get("baseline_final_label", "")),
        candidate_final_label=str(compare.get("candidate_final_label", "")),
        final_label_changed=bool(compare.get("final_label_changed", False)),
        confidence_delta=float(compare.get("confidence_delta", 0.0) or 0.0),
    )


def _to_payload(*, planner: PlannerExperimentResult, scoring: ScoringExperimentResult) -> dict[str, Any]:
    return {
        "rf14b_task": "RF14b-08",
        "generated_at_utc": _utc_now_iso(),
        "planner_experiment": {
            "baseline_run_id": planner.baseline_run_id,
            "candidate_run_id": planner.candidate_run_id,
            "baseline_model": planner.baseline_model,
            "candidate_model": planner.candidate_model,
            "baseline_selected_tests": planner.baseline_selected_tests,
            "candidate_selected_tests": planner.candidate_selected_tests,
            "selected_tests_changed": planner.selected_tests_changed,
            "baseline_hypothesis_ids": planner.baseline_hypothesis_ids,
            "candidate_hypothesis_ids": planner.candidate_hypothesis_ids,
            "hypothesis_ids_changed": planner.hypothesis_ids_changed,
        },
        "scoring_experiment": {
            "run_id": scoring.run_id,
            "baseline_profile": scoring.baseline_profile,
            "candidate_profile": scoring.candidate_profile,
            "scoring_compare_status": scoring.scoring_compare_status,
            "baseline_model_used": scoring.baseline_model_used,
            "candidate_model_used": scoring.candidate_model_used,
            "baseline_final_label": scoring.baseline_final_label,
            "candidate_final_label": scoring.candidate_final_label,
            "final_label_changed": scoring.final_label_changed,
            "confidence_delta": scoring.confidence_delta,
        },
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    planner = payload["planner_experiment"]
    scoring = payload["scoring_experiment"]
    text = (
        "# RF14b-08 — Experimentos de Modelos\n\n"
        f"Generado: `{payload['generated_at_utc']}`\n\n"
        "## Experimento 1 — Planner\n"
        f"- baseline_model: `{planner['baseline_model']}`\n"
        f"- candidate_model: `{planner['candidate_model']}`\n"
        f"- selected_tests_changed: `{planner['selected_tests_changed']}`\n"
        f"- hypothesis_ids_changed: `{planner['hypothesis_ids_changed']}`\n\n"
        "## Experimento 2 — Scoring\n"
        f"- baseline_profile: `{scoring['baseline_profile']}`\n"
        f"- candidate_profile: `{scoring['candidate_profile']}`\n"
        f"- scoring_compare_status: `{scoring['scoring_compare_status']}`\n"
        f"- baseline_model_used: `{scoring['baseline_model_used']}`\n"
        f"- candidate_model_used: `{scoring['candidate_model_used']}`\n"
        f"- final_label_changed: `{scoring['final_label_changed']}`\n"
        f"- confidence_delta: `{scoring['confidence_delta']}`\n"
    )
    path.write_text(text, encoding="utf-8")


def run_rf14b_experiments(
    *,
    run_id_prefix: str,
    models_config: Path,
    planner_baseline_model: str,
    planner_candidate_model: str,
    scoring_baseline_profile: str,
    scoring_candidate_profile: str,
    catalog_path: str,
) -> dict[str, Any]:
    out_dir = RUN_RESULTS_DIR / f"{run_id_prefix}-rf14b08"
    out_dir.mkdir(parents=True, exist_ok=True)

    planner_result = run_planner_experiment(
        run_id_prefix=run_id_prefix,
        base_models_config=models_config,
        planner_baseline_model=planner_baseline_model,
        planner_candidate_model=planner_candidate_model,
        catalog_path=catalog_path,
        out_dir=out_dir,
    )
    scoring_result = run_scoring_experiment(
        run_id_prefix=run_id_prefix,
        models_config=models_config,
        scoring_baseline_profile=scoring_baseline_profile,
        scoring_candidate_profile=scoring_candidate_profile,
    )

    payload = _to_payload(planner=planner_result, scoring=scoring_result)
    json_path = out_dir / "rf14b_experiments.json"
    md_path = out_dir / "rf14b_experiments.md"
    json_path.write_text(_stable_json(payload) + "\n", encoding="utf-8")
    _write_markdown(md_path, payload)
    payload["artifacts"] = {
        "json": str(json_path),
        "markdown": str(md_path),
        "dir": str(out_dir),
    }
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RF14b-08: ejecutar experimentos de modelos y comparar outputs")
    parser.add_argument("--run-id-prefix", default="rf14b-08", help="Prefijo de run_id para experimentos")
    parser.add_argument("--models-config", default="config/models.yaml", help="Ruta al models.yaml base")
    parser.add_argument("--planner-baseline-model", default="gpt-5.4-mini")
    parser.add_argument("--planner-candidate-model", default="gpt-5.4")
    parser.add_argument("--scoring-baseline-profile", default="default")
    parser.add_argument("--scoring-candidate-profile", default="conservative")
    parser.add_argument("--catalog-path", default="tests/catalog")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    payload = run_rf14b_experiments(
        run_id_prefix=str(args.run_id_prefix),
        models_config=(PROJECT_ROOT / str(args.models_config)).resolve(),
        planner_baseline_model=str(args.planner_baseline_model),
        planner_candidate_model=str(args.planner_candidate_model),
        scoring_baseline_profile=str(args.scoring_baseline_profile),
        scoring_candidate_profile=str(args.scoring_candidate_profile),
        catalog_path=str(args.catalog_path),
    )
    print(_stable_json(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
