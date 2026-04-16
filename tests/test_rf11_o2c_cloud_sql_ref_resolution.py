from __future__ import annotations

from pathlib import Path

import duckdb

from src.erp_fraud.catalog.test_execution import _resolve_sql_ref_path, run_test_sql_ref_generic


def test_rf11_o2c_sql_ref_resolves_relative_to_app_root_in_cloud(monkeypatch, tmp_path) -> None:
    app_root = tmp_path / "app"
    sql_file = app_root / "sql" / "tests" / "tst_o2c_clearing_anomaly.sql"
    sql_file.parent.mkdir(parents=True, exist_ok=True)
    sql_file.write_text("SELECT 1 AS company_code, 2 AS amount_local_currency", encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    monkeypatch.setattr("src.erp_fraud.catalog.test_execution.APP_ROOT", app_root)

    resolved = _resolve_sql_ref_path(
        test_spec={"id": "TST-O2C-CLEARING-ANOMALY", "logic": {"sql_ref": "sql/tests/tst_o2c_clearing_anomaly.sql"}},
        sql_ref="sql/tests/tst_o2c_clearing_anomaly.sql",
    )

    assert resolved == sql_file


def test_rf11_o2c_sql_ref_resolves_relative_to_catalog_yaml_dir(monkeypatch, tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    monkeypatch.setattr("src.erp_fraud.catalog.test_execution.APP_ROOT", tmp_path / "missing-app")

    catalog_dir = tmp_path / "tests" / "catalog_o2c"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = catalog_dir / "tst_o2c_discount_policy_breach.yaml"
    yaml_path.write_text("id: TST-O2C-DISCOUNT-POLICY-BREACH\n", encoding="utf-8")
    sql_file = catalog_dir / "sql" / "tests" / "tst_o2c_discount_policy_breach.sql"
    sql_file.parent.mkdir(parents=True, exist_ok=True)
    sql_file.write_text("SELECT 1 AS sales_order_id, 2 AS customer_id", encoding="utf-8")

    resolved = _resolve_sql_ref_path(
        test_spec={
            "id": "TST-O2C-DISCOUNT-POLICY-BREACH",
            "_catalog_source_path": str(yaml_path),
            "logic": {"sql_ref": "sql/tests/tst_o2c_discount_policy_breach.sql"},
        },
        sql_ref="sql/tests/tst_o2c_discount_policy_breach.sql",
    )

    assert resolved == sql_file


def test_rf11_o2c_run_test_sql_ref_generic_reads_sql_from_app_root(monkeypatch, tmp_path) -> None:
    app_root = tmp_path / "app"
    sql_file = app_root / "sql" / "tests" / "tst_o2c_delivery_quantity_mismatch.sql"
    sql_file.parent.mkdir(parents=True, exist_ok=True)
    sql_file.write_text(
        """
        SELECT
            '8000000001' AS delivery_id,
            '000010' AS delivery_item_id,
            '5000000001' AS sales_order_id,
            '000010' AS sales_order_item_id,
            15.0 AS delivered_quantity,
            10.0 AS ordered_quantity
        """,
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    monkeypatch.setattr("src.erp_fraud.catalog.test_execution.APP_ROOT", app_root)

    conn = duckdb.connect(":memory:")
    try:
        result = run_test_sql_ref_generic(
            {
                "id": "TST-O2C-DELIVERY-QUANTITY-MISMATCH",
                "version": "1.0.0",
                "fraud_type": "delivery_manipulation",
                "logic": {"sql_ref": "sql/tests/tst_o2c_delivery_quantity_mismatch.sql"},
                "expected_output": {"finding_fields": ["delivery_id", "delivery_item_id"]},
                "evidence_columns": [
                    "delivery_id",
                    "delivery_item_id",
                    "sales_order_id",
                    "sales_order_item_id",
                    "delivered_quantity",
                    "ordered_quantity",
                ],
            },
            conn=conn,
            schema_name="o2c",
            table_name="o2c_delivery",
        )
    finally:
        conn.close()

    assert result["status"] == "OK"
    assert result["metadata"]["implementation_type"] == "sql_ref"
    assert result["finding_count"] == 1
    assert result["rows"][0]["keys"] == {
        "delivery_id": "8000000001",
        "delivery_item_id": "000010",
    }
