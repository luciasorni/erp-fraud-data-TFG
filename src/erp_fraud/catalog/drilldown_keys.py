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
        "kreditor",
        "belegnummer",
        "position",
        "material",
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


def validate_minimum_keys_for_test_id(test_id: str, keys: Mapping[str, object]) -> None:
    """Valida que el mapping `keys` contiene las keys mínimas para ese test."""
    if not isinstance(keys, Mapping):
        raise TypeError("keys debe ser un mapping")
    required = get_minimum_keys_for_test_id(test_id)
    missing = [name for name in required if name not in keys]
    if missing:
        raise ValueError(
            f"keys incompletas para test_id={test_id}. Faltan: {missing}. "
            f"Requeridas: {list(required)}"
        )
