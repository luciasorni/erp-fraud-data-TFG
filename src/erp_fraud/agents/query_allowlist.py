"""Wrapper de queries por allowlist (query_template_id) sin SQL libre (RF15b-05)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..storage.duckdb_store import DEFAULT_DUCKDB_PATH, get_duckdb_connection


class QueryTemplateValidationError(ValueError):
    """Error de validación de configuración o parámetros de plantilla."""


class QueryTemplateNotAllowedError(PermissionError):
    """La plantilla solicitada no está en allowlist."""


def load_query_templates_config(path: str | Path = "config/query_templates.yaml") -> dict[str, Any]:
    """Carga y valida mínimamente el catálogo de query templates permitidas."""
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"No existe config de templates SQL: {resolved}")
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("No se puede leer YAML sin PyYAML instalado") from exc

    payload = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise QueryTemplateValidationError("query_templates.yaml debe contener objeto raíz")

    templates = payload.get("templates")
    if not isinstance(templates, dict) or not templates:
        raise QueryTemplateValidationError("query_templates.yaml: falta objeto 'templates'")

    for template_id, spec in templates.items():
        if not isinstance(template_id, str) or not template_id.strip():
            raise QueryTemplateValidationError("query_templates.yaml: template_id inválido")
        if not isinstance(spec, dict):
            raise QueryTemplateValidationError(f"query template inválida: {template_id}")
        sql = spec.get("sql")
        required_params = spec.get("required_params")
        if not isinstance(sql, str) or not sql.strip():
            raise QueryTemplateValidationError(f"{template_id}: 'sql' debe ser string no vacío")
        if not isinstance(required_params, list) or not required_params:
            raise QueryTemplateValidationError(
                f"{template_id}: 'required_params' debe ser lista no vacía"
            )
        for idx, name in enumerate(required_params):
            if not isinstance(name, str) or not name.strip():
                raise QueryTemplateValidationError(
                    f"{template_id}: 'required_params[{idx}]' debe ser string no vacío"
                )
        max_rows = spec.get("max_rows")
        if max_rows is None or isinstance(max_rows, bool) or int(max_rows) <= 0:
            raise QueryTemplateValidationError(f"{template_id}: 'max_rows' debe ser entero > 0")

    return payload


def _resolve_template(
    *,
    query_template_id: str,
    templates_config: dict[str, Any],
) -> dict[str, Any]:
    templates = templates_config.get("templates", {})
    if not isinstance(templates, dict):
        raise QueryTemplateValidationError("config templates inválida")
    if query_template_id not in templates:
        raise QueryTemplateNotAllowedError(
            f"query_template_id no permitida por allowlist: {query_template_id}"
        )
    template = templates[query_template_id]
    if not isinstance(template, dict):
        raise QueryTemplateValidationError(f"template inválida: {query_template_id}")
    return template


def _build_ordered_params(
    *,
    query_template_id: str,
    required_params: list[Any],
    params: dict[str, Any],
) -> list[Any]:
    if not isinstance(params, dict):
        raise QueryTemplateValidationError("params debe ser objeto con claves permitidas")
    missing = [name for name in required_params if name not in params]
    if missing:
        raise QueryTemplateValidationError(
            f"{query_template_id}: faltan parámetros requeridos: {', '.join(missing)}"
        )
    unknown = [name for name in params.keys() if name not in required_params]
    if unknown:
        raise QueryTemplateValidationError(
            f"{query_template_id}: parámetros no permitidos: {', '.join(sorted(unknown))}"
        )
    return [params[name] for name in required_params]


def execute_query_template(
    *,
    query_template_id: str,
    params: dict[str, Any],
    db_path: str | Path = DEFAULT_DUCKDB_PATH,
    conn: Any | None = None,
    templates_config: dict[str, Any] | None = None,
    templates_config_path: str | Path = "config/query_templates.yaml",
) -> dict[str, Any]:
    """Ejecuta una query template permitida con parámetros validados.

    No acepta SQL libre.
    """
    if not isinstance(query_template_id, str) or not query_template_id.strip():
        raise QueryTemplateValidationError("query_template_id debe ser string no vacío")

    cfg = templates_config or load_query_templates_config(templates_config_path)
    template = _resolve_template(query_template_id=query_template_id, templates_config=cfg)

    required_params = list(template["required_params"])
    ordered_params = _build_ordered_params(
        query_template_id=query_template_id,
        required_params=required_params,
        params=params,
    )

    sql = str(template["sql"])
    max_rows = int(template["max_rows"])

    own_connection = conn is None
    if own_connection:
        conn = get_duckdb_connection(db_path)
    assert conn is not None
    try:
        cur = conn.execute(sql, ordered_params)
        columns = [str(col[0]) for col in cur.description]
        rows = cur.fetchmany(max_rows)
    finally:
        if own_connection:
            conn.close()

    out_rows = [
        {columns[idx]: row[idx] for idx in range(len(columns))}
        for row in rows
    ]
    return {
        "query_template_id": query_template_id,
        "row_count": len(out_rows),
        "columns": columns,
        "rows": out_rows,
    }
