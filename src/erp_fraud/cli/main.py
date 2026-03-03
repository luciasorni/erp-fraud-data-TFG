"""CLI principal del proyecto ERP Fraud."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from ..storage.data_dictionary import DataDictionaryCompletenessError, check_dictionary_completeness


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
