"""CLI principal del proyecto ERP Fraud."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from ..catalog import drilldown, parse_entity_key
from ..storage.data_dictionary import DataDictionaryCompletenessError, check_dictionary_completeness
from ..storage.paths import ruta_run


def _run_validate_dictionary(args: argparse.Namespace) -> int:
    dictionary_path = Path(args.dictionary)
    if not dictionary_path.exists():
        print(f"ERROR: No existe dictionary JSON: {dictionary_path}", file=sys.stderr)
        return 2

    try:
        dictionary = json.loads(dictionary_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: No se pudo leer/parsear el dictionary JSON: {exc}", file=sys.stderr)
        return 2

    try:
        summary = check_dictionary_completeness(
            dictionary,
            catalog_path=args.catalog,
        )
    except DataDictionaryCompletenessError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.output_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "OK: dictionary completo "
            f"(tests={summary['tests_analyzed']}, "
            f"referenced_unique={summary['referenced_fields_unique']}, "
            f"documented={summary['documented_fields_total']})"
        )
    return 0


def _utc_timestamp_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _run_drilldown(args: argparse.Namespace) -> int:
    try:
        keys = parse_entity_key(args.entity_key)
    except Exception as exc:
        print(f"ERROR: entity_key inválido: {exc}", file=sys.stderr)
        return 2

    extra_filters: dict[str, str] = {}
    if args.transaktionsart:
        extra_filters["Transaktionsart"] = str(args.transaktionsart)

    try:
        rows = drilldown(
            test_id=args.test_id,
            keys=keys,
            db_path=args.db_path,
            schema_name=args.schema_name,
            table_name=args.table_name,
            limit_rows=int(args.limit_rows),
            order_direction=str(args.order_direction).upper(),
            extra_filters=extra_filters or None,
        )
    except Exception as exc:
        print(f"ERROR: no se pudo ejecutar drilldown: {exc}", file=sys.stderr)
        return 1

    payload = {
        "generated_at_utc": _utc_timestamp_iso(),
        "run_id": args.run_id,
        "test_id": args.test_id,
        "entity_key": args.entity_key,
        "keys": keys,
        "row_count": len(rows),
        "rows": rows,
    }

    output_path: Path | None = None
    if args.output:
        output_path = Path(args.output)
    elif args.save_default:
        safe_test_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in args.test_id)
        output_path = ruta_run(args.run_id) / f"drilldown_{safe_test_id}.json"

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"OK: drilldown rows={len(rows)} saved={output_path}")
        return 0

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="erp-fraud")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-dictionary",
        help="Valida que los campos usados por tests estén documentados",
    )
    validate_parser.add_argument(
        "--dictionary",
        default="data_dictionary.json",
        help="Ruta al data_dictionary.json (default: data_dictionary.json)",
    )
    validate_parser.add_argument(
        "--catalog",
        default="tests/catalog",
        help="Ruta al catálogo de tests (default: tests/catalog)",
    )
    validate_parser.add_argument(
        "--output-json",
        action="store_true",
        help="Imprime resumen en JSON en stdout",
    )
    validate_parser.set_defaults(handler=_run_validate_dictionary)

    drilldown_parser = subparsers.add_parser(
        "drilldown",
        help="Devuelve filas origen para un hallazgo usando test_id + entity_key",
    )
    drilldown_parser.add_argument("--run-id", required=True, help="Run ID de referencia")
    drilldown_parser.add_argument("--test-id", required=True, help="Test ID del catálogo")
    drilldown_parser.add_argument(
        "--entity-key",
        required=True,
        help="Clave de entidad en formato key=value|key2=value2",
    )
    drilldown_parser.add_argument(
        "--db-path",
        default="erp.duckdb",
        help="Ruta a DuckDB (default: erp.duckdb)",
    )
    drilldown_parser.add_argument(
        "--schema-name",
        default="main",
        help="Schema DuckDB (default: main)",
    )
    drilldown_parser.add_argument(
        "--table-name",
        default="fraud_1",
        help="Tabla base para drilldown (default: fraud_1)",
    )
    drilldown_parser.add_argument(
        "--limit-rows",
        type=int,
        default=200,
        help="Límite de filas de salida (default: 200, max cap interno 200)",
    )
    drilldown_parser.add_argument(
        "--order-direction",
        default="ASC",
        choices=["ASC", "DESC", "asc", "desc"],
        help="Orden de salida (ASC|DESC, default: ASC)",
    )
    drilldown_parser.add_argument(
        "--transaktionsart",
        default=None,
        help="Filtro opcional permitido por plantilla (Transaktionsart)",
    )
    drilldown_parser.add_argument(
        "--output",
        default=None,
        help="Ruta de salida JSON; si no se informa, imprime a stdout",
    )
    drilldown_parser.add_argument(
        "--save-default",
        action="store_true",
        help="Guarda en run_results/<run_id>/drilldown_<test_id>.json",
    )
    drilldown_parser.set_defaults(handler=_run_drilldown)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
