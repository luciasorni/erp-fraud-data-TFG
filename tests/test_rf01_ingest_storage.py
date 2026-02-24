from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pandas as pd
import pytest

from src.erp_fraud.ingest import (
    DatasetValidationError,
    TabularLoadError,
    TypeNormalizationError,
    calcular_dataset_hash,
    cargar_fichero_tabular_desde_zip,
    listar_ficheros_joint_datasets,
    limpiar_tecnicamente_dataframe,
    localizar_joint_datasets,
    normalizar_tipos_dataframe,
    validar_ficheros_esperados_joint_datasets,
)
from src.erp_fraud.storage import (
    IngestJsonLogger,
    build_run_metadata,
    build_schema_summary,
    get_duckdb_connection,
    load_table_to_duckdb,
    load_table_to_duckdb_with_stats,
    write_run_metadata_json,
    write_schema_summary_json,
)


def _make_zip(tmp_path: Path, files: dict[str, str | bytes]) -> Path:
    zip_path = tmp_path / "dataset.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return zip_path


def test_zip_reader_locates_and_lists_joint_datasets(tmp_path: Path) -> None:
    zip_path = _make_zip(
        tmp_path,
        {
            "erp_fraud_data/joint_datasets/a.csv": "x,y\n1,2\n",
            "erp_fraud_data/joint_datasets/README.txt": "ok",
            "__MACOSX/erp_fraud_data/._junk": "x",
        },
    )

    assert localizar_joint_datasets(zip_path) == "erp_fraud_data/joint_datasets/"
    assert listar_ficheros_joint_datasets(zip_path) == ["README.txt", "a.csv"]


def test_expected_files_validation_fails_with_clear_message(tmp_path: Path) -> None:
    zip_path = _make_zip(
        tmp_path,
        {"erp_fraud_data/joint_datasets/README.txt": "ok"},
    )

    with pytest.raises(DatasetValidationError, match="Faltan ficheros esperados"):
        validar_ficheros_esperados_joint_datasets(
            zip_path,
            expected_files=("README.txt", "missing.csv"),
        )


def test_tabular_loader_reads_csv_from_zip(tmp_path: Path) -> None:
    zip_path = _make_zip(
        tmp_path,
        {"erp_fraud_data/joint_datasets/demo.csv": "id;amount\n001;10,5\n002;20,0\n"},
    )

    df = cargar_fichero_tabular_desde_zip(zip_path, "demo.csv")

    assert list(df.columns) == ["id", "amount"]
    assert df.shape == (2, 2)
    assert str(df["id"].dtype) == "string"


def test_tabular_loader_raises_for_malformed_csv(tmp_path: Path) -> None:
    zip_path = _make_zip(
        tmp_path,
        {"erp_fraud_data/joint_datasets/bad.csv": 'a,b\n1,"x\n2,3\n'},
    )

    with pytest.raises(TabularLoadError, match="CSV mal formado|Error al cargar"):
        cargar_fichero_tabular_desde_zip(zip_path, "bad.csv")


def test_type_normalization_and_technical_cleaning() -> None:
    df = pd.DataFrame(
        {
            "fecha_transaccion": pd.Series(["24/02/2026", "  ", "bad"], dtype="string"),
            "importe_total": pd.Series(["10,50", " 20.75 ", "x"], dtype="string"),
            "doc_id": pd.Series(["001", " 002 ", "003"], dtype="string"),
            "note": pd.Series(["  hola  ", "NULL", ""], dtype="string"),
        }
    )

    cleaned, clean_summary = limpiar_tecnicamente_dataframe(df)
    norm, norm_summary = normalizar_tipos_dataframe(cleaned)

    assert clean_summary.trimmed_cells >= 2
    assert clean_summary.nulls_normalized >= 2
    assert "importe_total" in norm_summary.amount_columns
    assert "doc_id" in norm_summary.id_columns
    assert str(norm["importe_total"].dtype) == "Float64"
    assert str(norm["doc_id"].dtype) == "string"


def test_type_normalization_strict_mode_reports_parse_errors() -> None:
    df = pd.DataFrame(
        {
            "fecha_transaccion": ["24/02/2026", "bad-date"],
            "importe_total": ["1,00", "xx"],
            "doc_id": ["1", "2"],
        }
    )
    with pytest.raises(TypeNormalizationError, match="Tipos no parseables"):
        normalizar_tipos_dataframe(df, fail_on_parse_errors=True)


def test_dataset_hash_is_reproducible_for_same_zip(tmp_path: Path) -> None:
    zip_path = _make_zip(
        tmp_path,
        {
            "erp_fraud_data/joint_datasets/b.csv": "v\n2\n",
            "erp_fraud_data/joint_datasets/a.csv": "v\n1\n",
        },
    )
    r1 = calcular_dataset_hash(zip_path)
    r2 = calcular_dataset_hash(zip_path)

    assert r1.dataset_hash == r2.dataset_hash
    assert r1.files_hashed == 2
    assert r1.algorithm == "sha256"


def test_duckdb_load_stats_and_schema_summary(tmp_path: Path) -> None:
    db_path = tmp_path / "test.duckdb"
    conn = get_duckdb_connection(db_path)
    try:
        stats = load_table_to_duckdb_with_stats(
            "demo_table",
            pd.DataFrame({"id": ["1", "2"], "amount": [1.0, 2.0]}),
            conn=conn,
        )
        load_table_to_duckdb(
            "demo_table",
            pd.DataFrame({"id": ["3"], "amount": [3.0]}),
            mode="append",
            conn=conn,
        )
        total = conn.execute("SELECT COUNT(*) FROM demo_table").fetchone()[0]
        summary = build_schema_summary(conn=conn)
    finally:
        conn.close()

    assert stats.rows_loaded == 2
    assert stats.duration_ms >= 0
    assert total == 3
    assert summary["table_count"] == 1
    assert summary["tables"][0]["table_name"] == "demo_table"

    out = tmp_path / "schema_summary.json"
    write_schema_summary_json(out, db_path=db_path)
    assert out.exists()


def test_run_metadata_and_json_logger_generate_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    metadata = build_run_metadata(
        run_id="run-001",
        dataset_hash="hash-123",
        project_root=tmp_path,
        code_version="code-v1",
        tests_version="tests-v1",
        config_version="cfg-v1",
        timestamp_utc="2026-02-24T00:00:00+00:00",
    )
    assert metadata["run_id"] == "run-001"
    assert metadata["versions"]["code"] == "code-v1"

    metadata_path = tmp_path / "run_results" / "run-001" / "run_metadata.json"
    write_run_metadata_json(
        metadata_path,
        run_id="run-001",
        dataset_hash="hash-123",
        project_root=tmp_path,
        code_version="code-v1",
        tests_version="tests-v1",
        config_version="cfg-v1",
        timestamp_utc="2026-02-24T00:00:00+00:00",
    )
    loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert loaded["dataset_hash"] == "hash-123"

    logger = IngestJsonLogger.for_run("run-001")
    logger.log_ingest_start(dataset_hash="hash-123")
    logger.log_ingest_end(status="OK")
    log_path = tmp_path / "run_results" / "run-001" / "ingest_logs.jsonl"
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["event"] == "ingest_start"
    assert first["run_id"] == "run-001"
