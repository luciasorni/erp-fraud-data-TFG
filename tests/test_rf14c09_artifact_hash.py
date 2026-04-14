from __future__ import annotations

from pathlib import Path

from src.erp_fraud.storage.artifact_hash import compute_artifact_hash


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _scope_globs() -> dict[str, dict[str, tuple[str, ...]]]:
    return {
        "shared": {
            "prompts": ("prompts/shared/*.md",),
            "catalogs": (),
            "mappings": (),
            "docs_kb": ("docs/shared/*.md",),
        },
        "p2p": {
            "prompts": ("prompts/p2p/*.md",),
            "catalogs": ("tests/catalog/*.yaml",),
            "mappings": ("mappings/p2p/*.yaml",),
            "docs_kb": ("docs/p2p/*.md",),
        },
        "o2c": {
            "prompts": ("prompts/o2c/*.md",),
            "catalogs": ("tests/catalog_o2c/*.yaml",),
            "mappings": ("mappings/o2c/*.yaml",),
            "docs_kb": ("docs/o2c/*.md",),
        },
    }


def _prepare_tree(tmp_path: Path) -> None:
    _write(tmp_path / "prompts/shared/base.md", "shared prompt")
    _write(tmp_path / "docs/shared/base.md", "shared doc")

    _write(tmp_path / "prompts/p2p/prompt.md", "p2p prompt")
    _write(tmp_path / "tests/catalog/p2p.yaml", "id: P2P")
    _write(tmp_path / "mappings/p2p/map.yaml", "k: v")
    _write(tmp_path / "docs/p2p/doc.md", "p2p doc")

    _write(tmp_path / "prompts/o2c/prompt.md", "o2c prompt")
    _write(tmp_path / "tests/catalog_o2c/o2c.yaml", "id: O2C")
    _write(tmp_path / "mappings/o2c/map.yaml", "k: v2")
    _write(tmp_path / "docs/o2c/doc.md", "o2c doc")


def test_rf14c09_same_input_same_hash(tmp_path: Path) -> None:
    _prepare_tree(tmp_path)
    a = compute_artifact_hash(project_root=tmp_path, process_scope="p2p", scope_globs=_scope_globs())
    b = compute_artifact_hash(project_root=tmp_path, process_scope="p2p", scope_globs=_scope_globs())
    assert a["artifact_hash"] == b["artifact_hash"]
    assert a["manifest"] == b["manifest"]


def test_rf14c09_change_prompt_changes_hash(tmp_path: Path) -> None:
    _prepare_tree(tmp_path)
    before = compute_artifact_hash(project_root=tmp_path, process_scope="p2p", scope_globs=_scope_globs())
    _write(tmp_path / "prompts/p2p/prompt.md", "p2p prompt changed")
    after = compute_artifact_hash(project_root=tmp_path, process_scope="p2p", scope_globs=_scope_globs())
    assert before["artifact_hash"] != after["artifact_hash"]


def test_rf14c09_change_mapping_changes_hash(tmp_path: Path) -> None:
    _prepare_tree(tmp_path)
    before = compute_artifact_hash(project_root=tmp_path, process_scope="o2c", scope_globs=_scope_globs())
    _write(tmp_path / "mappings/o2c/map.yaml", "k: changed")
    after = compute_artifact_hash(project_root=tmp_path, process_scope="o2c", scope_globs=_scope_globs())
    assert before["artifact_hash"] != after["artifact_hash"]


def test_rf14c09_process_scope_changes_hash(tmp_path: Path) -> None:
    _prepare_tree(tmp_path)
    p2p = compute_artifact_hash(project_root=tmp_path, process_scope="p2p", scope_globs=_scope_globs())
    o2c = compute_artifact_hash(project_root=tmp_path, process_scope="o2c", scope_globs=_scope_globs())
    both = compute_artifact_hash(project_root=tmp_path, process_scope="both", scope_globs=_scope_globs())
    assert p2p["artifact_hash"] != o2c["artifact_hash"]
    assert both["artifact_hash"] not in {p2p["artifact_hash"], o2c["artifact_hash"]}


def test_rf14c09_fs_order_does_not_change_result(tmp_path: Path) -> None:
    _prepare_tree(tmp_path)
    _write(tmp_path / "tests/catalog/z_last.yaml", "id: LAST")
    _write(tmp_path / "tests/catalog/a_first.yaml", "id: FIRST")
    first = compute_artifact_hash(project_root=tmp_path, process_scope="p2p", scope_globs=_scope_globs())
    second = compute_artifact_hash(project_root=tmp_path, process_scope="p2p", scope_globs=_scope_globs())
    assert first["artifact_hash"] == second["artifact_hash"]

