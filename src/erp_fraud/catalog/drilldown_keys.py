"""Definición de keys mínimas para drilldown por test_id (RF06-01)."""

from __future__ import annotations

from copy import deepcopy
from typing import Mapping


# Keys mínimas necesarias para reconstruir filas origen por test.
DRILLDOWN_MIN_KEYS_BY_TEST_ID: dict[str, tuple[str, ...]] = {
    "TST-DUPLICATE-POSTINGS": (
        "kreditor",
        "belegnummer",
        "position",
        "betrag",
    ),
    "TST-UNUSUAL-AMOUNT-BY-VENDOR": (
        "kreditor",
        "betrag",
    ),
    "TST-ROUND-DOLLAR-PAYMENTS": (
        "kreditor",
        "belegnummer",
        "betrag",
    ),
    "TST-JUST-BELOW-AUTH-THRESHOLD": (
        "kreditor",
        "belegnummer",
        "betrag",
    ),
    "TST-SPLIT-PAYMENTS-NEAR-LIMIT": (
        "kreditor",
        "belegnummer",
    ),
    "TST-INVOICE-SEQUENCE-GAPS": (
        "kreditor",
        "belegnummer",
    ),
    "TST-NEGATIVE-QUANTITY-RECEIPTS": (
        "kreditor",
        "belegnummer",
        "material",
    ),
    "TST-DUPLICATE-MATERIAL-ITEMS": (
        "belegnummer",
        "position",
        "material",
    ),
    "TST-UNUSUAL-POSTING-TIMES": (
        "kreditor",
        "belegnummer",
        "erfassungsuhrzeit",
    ),
    "TST-LARGE-EVEN-DOLLAR-ENTRIES": (
        "kreditor",
        "belegnummer",
        "betrag",
    ),
    "TST-O2C-PRICE-OUTLIER": (
        "sales_order_id",
        "sales_order_item_id",
    ),
    "TST-O2C-DISCOUNT-POLICY-BREACH": (
        "sales_order_id",
        "sales_order_item_id",
    ),
    "TST-O2C-DELIVERY-QUANTITY-MISMATCH": (
        "delivery_id",
        "delivery_item_id",
    ),
    "TST-O2C-NEGATIVE-DELIVERY-QUANTITY": (
        "delivery_id",
        "delivery_item_id",
    ),
    "TST-O2C-CLEARING-ANOMALY": (
        "company_code",
        "receivable_document_id",
        "fiscal_year",
    ),
    "TST-O2C-INVOICE-AMOUNT-ANOMALY": (
        "company_code",
        "accounting_document_id",
        "fiscal_year",
    ),
    "TST-O2C-INVOICE-DATE-SEQUENCE": (
        "company_code",
        "accounting_document_id",
        "fiscal_year",
    ),
}


def get_drilldown_min_keys_by_test_id() -> dict[str, tuple[str, ...]]:
    """Devuelve copia del mapa de keys mínimas por test_id."""
    return deepcopy(DRILLDOWN_MIN_KEYS_BY_TEST_ID)


def get_minimum_keys_for_test_id(test_id: str) -> tuple[str, ...]:
    """Devuelve keys mínimas requeridas para un test_id."""
    key = str(test_id or "").strip()
    if not key:
        raise ValueError("test_id debe ser string no vacío")
    if key not in DRILLDOWN_MIN_KEYS_BY_TEST_ID:
        raise KeyError(f"test_id sin definición de keys mínimas: {key}")
    return tuple(DRILLDOWN_MIN_KEYS_BY_TEST_ID[key])


def normalize_drilldown_keys(keys: Mapping[str, object]) -> dict[str, str]:
    """Normaliza keys de drilldown a strings no vacíos."""
    if not isinstance(keys, Mapping):
        raise TypeError("keys debe ser un mapping")
    normalized: dict[str, str] = {}
    for raw_key, raw_value in keys.items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        value = str(raw_value).strip() if raw_value is not None else ""
        if value.lower() in {"none", "null"}:
            value = ""
        if value:
            normalized[key] = value
    return normalized


def get_missing_or_empty_minimum_keys_for_test_id(test_id: str, keys: Mapping[str, object]) -> list[str]:
    required = get_minimum_keys_for_test_id(test_id)
    normalized = normalize_drilldown_keys(keys)
    return [name for name in required if name not in normalized]


def validate_minimum_keys_for_test_id(test_id: str, keys: Mapping[str, object]) -> None:
    """Valida que el mapping `keys` contiene las keys mínimas para ese test."""
    if not isinstance(keys, Mapping):
        raise TypeError("keys debe ser un mapping")
    required = get_minimum_keys_for_test_id(test_id)
    missing = get_missing_or_empty_minimum_keys_for_test_id(test_id, keys)
    if missing:
        raise ValueError(
            f"keys incompletas para test_id={test_id}. Faltan: {missing}. "
            f"Requeridas: {list(required)}"
        )
