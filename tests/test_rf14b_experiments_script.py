from __future__ import annotations

import json
from pathlib import Path
import sys

import scripts.run_rf14b_experiments as rf14b_exp


def test_rf14b08_experiments_script_generates_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(rf14b_exp, "RUN_RESULTS_DIR", tmp_path / "run_results")

    payload = rf14b_exp.run_rf14b_experiments(
        run_id_prefix="rf14b-08-test",
        models_config=Path("config/models.yaml").resolve(),
        planner_baseline_model="gpt-5.4-mini",
        planner_candidate_model="gpt-5.4",
        scoring_baseline_profile="default",
        scoring_candidate_profile="conservative",
        catalog_path="tests/catalog",
    )

    assert payload["rf14b_task"] == "RF14b-08"

    planner = payload["planner_experiment"]
    assert planner["baseline_model"] == "gpt-5.4-mini"
    assert planner["candidate_model"] == "gpt-5.4"
    assert isinstance(planner["baseline_selected_tests"], list)
    assert isinstance(planner["candidate_selected_tests"], list)

    scoring = payload["scoring_experiment"]
    assert scoring["baseline_profile"] == "default"
    assert scoring["candidate_profile"] == "conservative"
    assert scoring["scoring_compare_status"] == "OK"
    assert isinstance(scoring["final_label_changed"], bool)

    artifacts = payload["artifacts"]
    json_path = Path(artifacts["json"])
    md_path = Path(artifacts["markdown"])
    assert json_path.exists()
    assert md_path.exists()

    stored = json.loads(json_path.read_text(encoding="utf-8"))
    assert stored["rf14b_task"] == "RF14b-08"
    assert stored["scoring_experiment"]["scoring_compare_status"] == "OK"


def test_rf14b08_experiments_script_main_cli(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(rf14b_exp, "RUN_RESULTS_DIR", tmp_path / "run_results")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_rf14b_experiments.py",
            "--run-id-prefix",
            "rf14b-08-cli",
            "--models-config",
            "config/models.yaml",
        ],
    )
    exit_code = rf14b_exp.main()
    assert exit_code == 0

    out_dir = tmp_path / "run_results" / "rf14b-08-cli-rf14b08"
    assert (out_dir / "rf14b_experiments.json").exists()
    assert (out_dir / "rf14b_experiments.md").exists()
