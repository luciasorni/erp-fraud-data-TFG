"""Convención común de `entity_key` para hallazgos (RF05-03)."""

from __future__ import annotations

from typing import Mapping

ENTITY_KEY_SEPARATOR = "|"
ENTITY_KEY_ASSIGN_SEPARATOR = "="


def build_entity_key(keys: Mapping[str, str]) -> str:
    """Construye `entity_key` estable a partir de un mapping de claves.

    Reglas:
    - Orden lexicográfico por nombre de clave.
    - Formato `key=value` unido por `|`.
    - No se permiten claves/valores vacíos ni separadores reservados.
    """
    if not isinstance(keys, Mapping) or len(keys) == 0:
        raise ValueError("keys debe ser un mapping no vacío")

    parts: list[str] = []
    for key in sorted(keys.keys()):
        value = keys[key]
        if not isinstance(key, str) or not key.strip():
            raise ValueError("cada key en keys debe ser string no vacío")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"valor inválido para key '{key}': debe ser string no vacío")
        if ENTITY_KEY_SEPARATOR in key or ENTITY_KEY_ASSIGN_SEPARATOR in key:
            raise ValueError(f"key '{key}' contiene separadores reservados")
        if ENTITY_KEY_SEPARATOR in value or ENTITY_KEY_ASSIGN_SEPARATOR in value:
            raise ValueError(f"value para '{key}' contiene separadores reservados")
        parts.append(f"{key}{ENTITY_KEY_ASSIGN_SEPARATOR}{value}")

    return ENTITY_KEY_SEPARATOR.join(parts)


def parse_entity_key(entity_key: str) -> dict[str, str]:
    """Parsea un `entity_key` a diccionario de claves."""
    if not isinstance(entity_key, str) or not entity_key.strip():
        raise ValueError("entity_key debe ser string no vacío")

    parsed: dict[str, str] = {}
    chunks = entity_key.split(ENTITY_KEY_SEPARATOR)
    for chunk in chunks:
        if ENTITY_KEY_ASSIGN_SEPARATOR not in chunk:
            raise ValueError(f"segmento inválido en entity_key: '{chunk}'")
        key, value = chunk.split(ENTITY_KEY_ASSIGN_SEPARATOR, 1)
        if not key or not value:
            raise ValueError(f"segmento inválido en entity_key: '{chunk}'")
        if key in parsed:
            raise ValueError(f"clave duplicada en entity_key: '{key}'")
        parsed[key] = value
    return parsed

