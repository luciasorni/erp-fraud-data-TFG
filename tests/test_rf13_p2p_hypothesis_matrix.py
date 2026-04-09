from __future__ import annotations

from pathlib import Path

from src.erp_fraud.storage.p2p_hypothesis_matrix import validate_p2p_hypothesis_matrix


def test_rf13_p2p_hypothesis_matrix_ok() -> None:
    out = validate_p2p_hypothesis_matrix()
    assert out["status"] == "OK"
    assert int(out["rows_total"]) >= 10
    assert int(out["rows_total"]) == int(out["rows_valid"])


def test_rf13_p2p_hypothesis_matrix_fails_on_unknown_test_id(tmp_path: Path) -> None:
    src = Path("docs/p2p/artifacts/rf13_p2p_hypothesis_matrix.csv")
    bad = tmp_path / "bad_matrix.csv"
    content = src.read_text(encoding="utf-8")
    content = content.replace("TST-DUPLICATE-POSTINGS", "TST-NO-EXISTE", 1)
    bad.write_text(content, encoding="utf-8")

    out = validate_p2p_hypothesis_matrix(matrix_csv_path=bad)
    assert out["status"] == "ERROR"
    assert any("test_id no existe en catálogo" in str(err) for err in out.get("errors", []))

