from __future__ import annotations

import argparse

from src.erp_fraud.cli.main import _resolve_run_settings, build_parser
from src.erp_fraud.cli.main import _filter_catalog_test_ids


def _sample_specs() -> list[dict]:
    return [
        {
            "id": "TST-DUPLICATE-POSTINGS",
            "fraud_type": "duplicate_payment",
            "tags": ["p2p", "acfe", "duplicates"],
        },
        {
            "id": "TST-UNUSUAL-AMOUNT-BY-VENDOR",
            "fraud_type": "amount_anomaly",
            "tags": ["p2p", "acfe", "amount"],
        },
        {
            "id": "TST-ROUND-DOLLAR-PAYMENTS",
            "fraud_type": "suspicious_payment_pattern",
            "tags": ["p2p", "acfe", "pattern"],
        },
    ]


def test_filter_catalog_test_ids_none_when_no_filters() -> None:
    assert _filter_catalog_test_ids(test_specs=_sample_specs()) is None


def test_filter_catalog_test_ids_by_fraud_type() -> None:
    out = _filter_catalog_test_ids(
        test_specs=_sample_specs(),
        select_fraud_types=["amount_anomaly"],
    )
    assert out == ["TST-UNUSUAL-AMOUNT-BY-VENDOR"]


def test_filter_catalog_test_ids_by_tag() -> None:
    out = _filter_catalog_test_ids(
        test_specs=_sample_specs(),
        select_tags=["duplicates"],
    )
    assert out == ["TST-DUPLICATE-POSTINGS"]


def test_filter_catalog_test_ids_combines_select_tests_and_filters() -> None:
    out = _filter_catalog_test_ids(
        test_specs=_sample_specs(),
        select_tests=["TST-DUPLICATE-POSTINGS", "TST-ROUND-DOLLAR-PAYMENTS"],
        select_tags=["pattern"],
    )
    assert out == ["TST-ROUND-DOLLAR-PAYMENTS"]


def test_rf13_cli_selection_flags_are_parsed() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "run",
            "--input-zip",
            "erp_fraud_data.zip",
            "--select-fraud-types",
            "duplicate_payment,amount_anomaly",
            "--select-tags",
            "p2p,acfe",
        ]
    )
    assert isinstance(args, argparse.Namespace)
    settings = _resolve_run_settings(args)
    assert settings["select_fraud_types"] == ["duplicate_payment", "amount_anomaly"]
    assert settings["select_tags"] == ["p2p", "acfe"]


def test_rf11_07_cli_process_family_is_parsed() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "run",
            "--input-zip",
            "erp_fraud_data.zip",
            "--process-family",
            "o2c",
        ]
    )
    settings = _resolve_run_settings(args)
    assert settings["process_family"] == "o2c"
