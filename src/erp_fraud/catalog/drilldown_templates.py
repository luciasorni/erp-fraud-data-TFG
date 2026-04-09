"""Referencias de plantillas seguras para drilldown (RF06-02)."""

from __future__ import annotations

from typing import Mapping


DRILLDOWN_QUERY_ID_BY_TEST_ID: dict[str, str] = {
    "TST-DUPLICATE-POSTINGS": "drilldown_duplicate_postings_v1",
    "TST-UNUSUAL-AMOUNT-BY-VENDOR": "drilldown_unusual_amount_by_vendor_v1",
    "TST-ROUND-DOLLAR-PAYMENTS": "drilldown_round_dollar_payments_v1",
    "TST-JUST-BELOW-AUTH-THRESHOLD": "drilldown_just_below_auth_threshold_v1",
    "TST-SPLIT-PAYMENTS-NEAR-LIMIT": "drilldown_split_payments_near_limit_v1",
    "TST-INVOICE-SEQUENCE-GAPS": "drilldown_invoice_sequence_gaps_v1",
    "TST-NEGATIVE-QUANTITY-RECEIPTS": "drilldown_negative_quantity_receipts_v1",
    "TST-DUPLICATE-MATERIAL-ITEMS": "drilldown_duplicate_material_items_v1",
    "TST-UNUSUAL-POSTING-TIMES": "drilldown_unusual_posting_times_v1",
    "TST-LARGE-EVEN-DOLLAR-ENTRIES": "drilldown_large_even_dollar_entries_v1",
    "TST-O2C-PRICE-OUTLIER": "drilldown_o2c_price_outlier_v1",
    "TST-O2C-DISCOUNT-POLICY-BREACH": "drilldown_o2c_discount_policy_breach_v1",
    "TST-O2C-DELIVERY-QUANTITY-MISMATCH": "drilldown_o2c_delivery_quantity_mismatch_v1",
    "TST-O2C-NEGATIVE-DELIVERY-QUANTITY": "drilldown_o2c_negative_delivery_quantity_v1",
    "TST-O2C-CLEARING-ANOMALY": "drilldown_o2c_clearing_anomaly_v1",
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
