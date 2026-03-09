"""Referencias de plantillas seguras para drilldown (RF06-02)."""

from __future__ import annotations

from typing import Mapping


DRILLDOWN_QUERY_ID_BY_TEST_ID: dict[str, str] = {
    "TST-DUPLICATE-POSTINGS": "drilldown_duplicate_postings_v1",
    "TST-UNUSUAL-AMOUNT-BY-VENDOR": "drilldown_unusual_amount_by_vendor_v1",
}


def get_drilldown_query_id_for_test_id(test_id: str) -> str:
    key = str(test_id or "").strip()
    if not key:
        raise ValueError("test_id debe ser string no vacío")
    if key not in DRILLDOWN_QUERY_ID_BY_TEST_ID:
        raise KeyError(f"test_id sin query_id de drilldown: {key}")
    return DRILLDOWN_QUERY_ID_BY_TEST_ID[key]


def build_drilldown_template_ref(
    *,
    test_id: str,
    keys: Mapping[str, str],
) -> dict[str, object]:
    """Construye referencia segura para drilldown (query_id + params)."""
    return {
        "query_id": get_drilldown_query_id_for_test_id(test_id),
        "params": {str(k): str(v) for k, v in keys.items()},
    }

