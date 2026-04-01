from __future__ import annotations

from pathlib import Path


def test_rf15_explainer_prompt_mentions_no_inventions_and_required_citations() -> None:
    content = Path("prompts/explainer.md").read_text(encoding="utf-8")
    assert "NO inventes columnas" in content
    assert "test_id" in content
    assert "keys" in content
    assert "evidence_columns" in content


def test_rf15_explainer_prompt_mentions_kbsearchtool_and_acfe_citations() -> None:
    content = Path("prompts/explainer.md").read_text(encoding="utf-8")
    assert "KBSearchTool" in content
    assert "source_id" in content
    assert "chunk_id" in content
