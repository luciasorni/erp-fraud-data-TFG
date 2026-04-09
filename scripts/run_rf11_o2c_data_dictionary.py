#!/usr/bin/env python3
# ruff: noqa: E402
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.erp_fraud.storage.o2c_data_dictionary import (
    build_o2c_data_dictionary,
    write_o2c_data_dictionary_json,
    write_o2c_data_dictionary_markdown,
)


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"rf11-o2c-dd-{stamp}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_rf11_o2c_data_dictionary",
        description="Genera data dictionary O2C mínimo desde schema+mapping (RF11-10).",
    )
    parser.add_argument("--run-id", default=None, help="Run ID para evidencias (default: autogenerado)")
    parser.add_argument("--out-dir", default="run_results", help="Directorio base para evidencias")
    parser.add_argument(
        "--canonical-schema-config",
        default="config/canonical_schema_o2c.yaml",
        help="Config schema canónico O2C",
    )
    parser.add_argument(
        "--mapping-config",
        default="config/column_mapping_o2c.yaml",
        help="Config mapping O2C",
    )
    parser.add_argument(
        "--write-docs-artifacts",
        action="store_true",
        help="Además de run_results, escribe copia en docs/o2c/artifacts/",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    run_id = str(args.run_id).strip() if args.run_id else _default_run_id()
    run_dir = Path(args.out_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    json_path = run_dir / "rf11_10_o2c_data_dictionary.json"
    md_path = run_dir / "rf11_10_o2c_data_dictionary.md"

    payload = build_o2c_data_dictionary(
        canonical_schema_config_path=args.canonical_schema_config,
        mapping_config_path=args.mapping_config,
    )
    write_o2c_data_dictionary_json(
        json_path,
        canonical_schema_config_path=args.canonical_schema_config,
        mapping_config_path=args.mapping_config,
    )
    write_o2c_data_dictionary_markdown(md_path, dictionary_payload=payload)

    if args.write_docs_artifacts:
        docs_dir = Path("docs/o2c/artifacts")
        docs_dir.mkdir(parents=True, exist_ok=True)
        write_o2c_data_dictionary_json(
            docs_dir / "rf11_10_o2c_data_dictionary.json",
            canonical_schema_config_path=args.canonical_schema_config,
            mapping_config_path=args.mapping_config,
        )
        write_o2c_data_dictionary_markdown(
            docs_dir / "rf11_10_o2c_data_dictionary.md",
            dictionary_payload=payload,
        )

    print(f"OK RF11-10 data dictionary: {json_path}")
    print(f"OK RF11-10 data dictionary: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
