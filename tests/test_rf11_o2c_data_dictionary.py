from __future__ import annotations

import json
from pathlib import Path

from src.erp_fraud.storage.o2c_data_dictionary import (
    build_o2c_data_dictionary,
    write_o2c_data_dictionary_json,
    write_o2c_data_dictionary_markdown,
)


def test_rf11_10_build_o2c_data_dictionary_has_min_entries() -> None:
    payload = build_o2c_data_dictionary()
    assert payload["scope"]["process"] == "O2C"
    entries = payload.get("entries", [])
    assert isinstance(entries, list) and entries
    tables = {str(e.get("table", "")) for e in entries if isinstance(e, dict)}
    assert "o2c_order" in tables
    assert "o2c_delivery" in tables
    assert "o2c_invoice" in tables
    assert "o2c_collection" in tables
    assert "o2c_customer" in tables


def test_rf11_10_write_o2c_data_dictionary_json_and_md(tmp_path: Path) -> None:
    json_path = tmp_path / "o2c_dd.json"
    md_path = tmp_path / "o2c_dd.md"
    write_o2c_data_dictionary_json(json_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["scope"]["process"] == "O2C"
    assert isinstance(payload.get("entries", []), list)

    write_o2c_data_dictionary_markdown(md_path, dictionary_payload=payload)
    content = md_path.read_text(encoding="utf-8")
    assert "# Data Dictionary O2C" in content
    assert "## Tabla: `o2c_order`" in content

