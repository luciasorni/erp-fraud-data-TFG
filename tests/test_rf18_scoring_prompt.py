from __future__ import annotations

from pathlib import Path


def test_rf18_scoring_prompt_mentions_required_input_contract() -> None:
    content = Path("prompts/scoring.md").read_text(encoding="utf-8")
    assert "hypotheses" in content
    assert "findings" in content
    assert "acfe_snippets" in content


def test_rf18_scoring_prompt_mentions_score_schema_fields() -> None:
    content = Path("prompts/scoring.md").read_text(encoding="utf-8")
    for field in (
        "score_schema_version",
        "generated_at_utc",
        "fraud_type_probs",
        "final_label",
        "confidence",
        "evidence_summary",
        "model_used",
    ):
        assert field in content
