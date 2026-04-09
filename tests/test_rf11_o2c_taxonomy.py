from __future__ import annotations

from pathlib import Path

from src.erp_fraud.storage.o2c_taxonomy import validate_o2c_taxonomy_alignment


def test_rf11_12_o2c_taxonomy_alignment_ok() -> None:
    payload = validate_o2c_taxonomy_alignment()
    assert payload["status"] == "OK"
    assert isinstance(payload.get("mapped_rows"), list) and payload["mapped_rows"]


def test_rf11_12_o2c_taxonomy_alignment_fails_when_missing_mapping(tmp_path: Path) -> None:
    tax_path = tmp_path / "taxonomy_bad.yaml"
    tax_path.write_text(
        """
version: 1.0.0
branches:
  - id: corruption
    label: Corruption
internal_fraud_type_to_branch:
  price_manipulation: corruption
""".strip()
        + "\n",
        encoding="utf-8",
    )

    payload = validate_o2c_taxonomy_alignment(taxonomy_config_path=tax_path)
    assert payload["status"] == "ERROR"
    assert any("fraud_type sin mapping" in str(err) for err in payload["errors"])
