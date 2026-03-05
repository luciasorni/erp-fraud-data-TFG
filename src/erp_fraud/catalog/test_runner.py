"""Runner básico de tests de catálogo (RF04-01)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter
import threading
import traceback
from typing import Any

from ..storage.duckdb_store import DEFAULT_DUCKDB_PATH
from ..storage.paths import ruta_run
from .test_execution import run_test_duplicate_postings, run_test_unusual_amount_by_vendor
from .test_spec_loader import load_test_specs_from_catalog


class TestRunner:
    """Ejecutor de tests del catálogo."""

    def __init__(
        self,
        *,
        db_path: str | Path = DEFAULT_DUCKDB_PATH,
        schema_name: str = "main",
        table_name: str = "fraud_1",
    ) -> None:
        self.db_path = db_path
        self.schema_name = schema_name
        self.table_name = table_name
        self.last_run_metrics: dict[str, Any] = {}
        self.last_results: list[dict[str, Any]] = []
        self.last_log_path: Path | None = None

    @staticmethod
    def _utc_timestamp_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def _build_error_result(
        self,
        test_spec: dict[str, Any],
        *,
        duration_ms: int,
        error: Exception,
        traceback_lines: list[str] | None = None,
    ) -> dict[str, Any]:
        test_id = str(test_spec.get("id", ""))
        tb_tail = traceback_lines
        if tb_tail is None:
            tb_tail = traceback.format_exc().strip().splitlines()[-5:]
        return {
            "result_schema_version": "1.0.0",
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "test_id": test_id,
            "test_version": str(test_spec.get("version", "")),
            "fraud_type": str(test_spec.get("fraud_type", "")),
            "status": "ERROR",
            "finding_count": 0,
            "duration_ms": int(duration_ms),
            "runner_duration_ms": int(duration_ms),
            "columns": [],
            "rows": [],
            "error_summary": f"{type(error).__name__}: {error}",
            "error_traceback_tail": tb_tail,
            "metadata": {
                "implementation_type": str(test_spec.get("logic", {}).get("implementation_type", "")),
                "executed_on": f"{self.schema_name}.{self.table_name}",
            },
        }

    def _build_timeout_result(
        self,
        test_spec: dict[str, Any],
        *,
        duration_ms: int,
        timeout_ms: int,
    ) -> dict[str, Any]:
        return {
            "result_schema_version": "1.0.0",
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "test_id": str(test_spec.get("id", "")),
            "test_version": str(test_spec.get("version", "")),
            "fraud_type": str(test_spec.get("fraud_type", "")),
            "status": "TIMEOUT",
            "finding_count": 0,
            "duration_ms": int(duration_ms),
            "runner_duration_ms": int(duration_ms),
            "columns": [],
            "rows": [],
            "error_summary": f"TimeoutError: test excedió timeout_ms={timeout_ms}",
            "metadata": {
                "implementation_type": str(test_spec.get("logic", {}).get("implementation_type", "")),
                "executed_on": f"{self.schema_name}.{self.table_name}",
            },
        }

    @staticmethod
    def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def _log_test_event(
        self,
        *,
        log_path: Path | None,
        run_id: str | None,
        event: str,
        test_id: str,
        status: str | None = None,
        duration_ms: int | None = None,
        error_summary: str | None = None,
    ) -> None:
        if log_path is None:
            return
        record: dict[str, Any] = {
            "timestamp_utc": self._utc_timestamp_iso(),
            "level": "INFO" if not error_summary else "ERROR",
            "event": event,
            "run_id": run_id or "",
            "test_id": test_id,
        }
        if status is not None:
            record["status"] = status
        if duration_ms is not None:
            record["duration_ms"] = int(duration_ms)
        if error_summary:
            record["error_summary"] = error_summary
        self._append_jsonl(log_path, record)

    def _run_test_with_timeout(
        self,
        test_spec: dict[str, Any],
        *,
        timeout_ms: int,
    ) -> dict[str, Any]:
        holder: dict[str, Any] = {}
        started_test = perf_counter()

        def _target() -> None:
            try:
                holder["result"] = self.run(test_spec)
            except Exception as exc:  # pragma: no cover - cubierto vía run_all
                holder["error"] = exc
                holder["traceback"] = traceback.format_exc().strip().splitlines()[-5:]

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join(timeout=timeout_ms / 1000.0)

        if thread.is_alive():
            duration_ms = int((perf_counter() - started_test) * 1000)
            return self._build_timeout_result(
                test_spec,
                duration_ms=duration_ms,
                timeout_ms=timeout_ms,
            )

        if "error" in holder:
            duration_ms = int((perf_counter() - started_test) * 1000)
            return self._build_error_result(
                test_spec,
                duration_ms=duration_ms,
                error=holder["error"],
                traceback_lines=holder.get("traceback"),
            )

        return dict(holder.get("result", {}))

    def run(self, test_spec: dict[str, Any]) -> dict[str, Any]:
        """Ejecuta un test del catálogo y devuelve resultado estándar."""
        started = perf_counter()
        test_id = str(test_spec.get("id", ""))
        if test_id == "TST-DUPLICATE-POSTINGS":
            result = run_test_duplicate_postings(
                test_spec,
                db_path=self.db_path,
                schema_name=self.schema_name,
                table_name=self.table_name,
            )
        elif test_id == "TST-UNUSUAL-AMOUNT-BY-VENDOR":
            result = run_test_unusual_amount_by_vendor(
                test_spec,
                db_path=self.db_path,
                schema_name=self.schema_name,
                table_name=self.table_name,
            )
        else:
            raise NotImplementedError(f"Test no soportado por TestRunner: {test_id}")

        runner_duration_ms = int((perf_counter() - started) * 1000)
        result["runner_duration_ms"] = runner_duration_ms
        return result

    def _load_catalog_specs(
        self,
        *,
        catalog_path: str | Path,
        validate_schema: bool,
    ) -> list[dict[str, Any]]:
        specs = load_test_specs_from_catalog(catalog_path, validate_schema=validate_schema)
        return [dict(spec) for spec in specs]

    def _build_allowlist_map(
        self,
        *,
        catalog_path: str | Path,
        validate_schema: bool,
    ) -> dict[str, dict[str, Any]]:
        specs = self._load_catalog_specs(catalog_path=catalog_path, validate_schema=validate_schema)
        allowlist: dict[str, dict[str, Any]] = {}
        for spec in specs:
            test_id = str(spec.get("id", "")).strip()
            if not test_id:
                continue
            if test_id in allowlist:
                raise ValueError(f"Test ID duplicado en catálogo: {test_id}")
            allowlist[test_id] = spec
        return allowlist

    def run_all(
        self,
        selected_tests: list[dict[str, Any]] | list[str] | None = None,
        *,
        catalog_path: str | Path = "tests/catalog",
        validate_schema: bool = True,
        timeout_ms: int | None = None,
        run_id: str | None = None,
        log_path: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        """Ejecuta tests respetando lista blanca de IDs del catálogo.

        - `selected_tests=None`: ejecuta todos los tests del catálogo.
        - `selected_tests=[\"TST-...\"]`: ejecuta IDs seleccionados (orden de entrada).
        - `selected_tests=[{...spec...}]`: ejecuta specs seleccionados validando que su ID
          exista en el catálogo.
        """
        started_total = perf_counter()
        started_selection = perf_counter()
        allowlist = self._build_allowlist_map(
            catalog_path=catalog_path,
            validate_schema=validate_schema,
        )

        if selected_tests is None:
            specs_to_run = [allowlist[test_id] for test_id in sorted(allowlist.keys())]
        elif len(selected_tests) == 0:
            specs_to_run = []
        elif isinstance(selected_tests[0], str):
            selected_ids = [str(test_id) for test_id in selected_tests]  # type: ignore[index]
            unknown_ids = [test_id for test_id in selected_ids if test_id not in allowlist]
            if unknown_ids:
                raise ValueError(
                    "Test IDs fuera de lista blanca (catálogo): " + ", ".join(sorted(set(unknown_ids)))
                )
            specs_to_run = [allowlist[test_id] for test_id in selected_ids]
        else:
            input_specs = [dict(spec) for spec in selected_tests]  # type: ignore[arg-type]
            unknown_ids: list[str] = []
            for spec in input_specs:
                test_id = str(spec.get("id", "")).strip()
                if test_id not in allowlist:
                    unknown_ids.append(test_id or "<sin-id>")
            if unknown_ids:
                raise ValueError(
                    "Test IDs fuera de lista blanca (catálogo): " + ", ".join(sorted(set(unknown_ids)))
                )
            specs_to_run = input_specs

        selection_duration_ms = int((perf_counter() - started_selection) * 1000)
        started_execution = perf_counter()
        if timeout_ms is not None and timeout_ms <= 0:
            raise ValueError("timeout_ms debe ser > 0 si se informa")

        resolved_log_path: Path | None
        if log_path is not None:
            resolved_log_path = Path(log_path)
        elif run_id:
            resolved_log_path = ruta_run(run_id) / "test_runner_logs.jsonl"
        else:
            resolved_log_path = None

        self.last_log_path = resolved_log_path
        results: list[dict[str, Any]] = []
        for spec in specs_to_run:
            test_id = str(spec.get("id", ""))
            self._log_test_event(
                log_path=resolved_log_path,
                run_id=run_id,
                event="test_start",
                test_id=test_id,
            )
            if timeout_ms is not None:
                result = self._run_test_with_timeout(spec, timeout_ms=timeout_ms)
            else:
                started_test = perf_counter()
                try:
                    result = self.run(spec)
                except Exception as exc:
                    test_duration_ms = int((perf_counter() - started_test) * 1000)
                    result = self._build_error_result(
                        spec,
                        duration_ms=test_duration_ms,
                        error=exc,
                    )
            results.append(result)
            self._log_test_event(
                log_path=resolved_log_path,
                run_id=run_id,
                event="test_end",
                test_id=test_id,
                status=str(result.get("status", "")),
                duration_ms=int(result.get("runner_duration_ms", result.get("duration_ms", 0)) or 0),
                error_summary=str(result.get("error_summary", "")) or None,
            )
        execution_duration_ms = int((perf_counter() - started_execution) * 1000)
        total_duration_ms = int((perf_counter() - started_total) * 1000)

        self.last_run_metrics = {
            "started_at_utc": self._utc_timestamp_iso(),
            "tests_count": len(results),
            "phase_duration_ms": {
                "selection": selection_duration_ms,
                "execution": execution_duration_ms,
                "total": total_duration_ms,
            },
            "tests_duration_ms": [
                {
                    "test_id": str(result.get("test_id", "")),
                    "duration_ms": int(result.get("duration_ms", 0)),
                    "runner_duration_ms": int(result.get("runner_duration_ms", 0)),
                    "status": str(result.get("status", "")),
                }
                for result in results
            ],
        }
        self.last_results = [dict(result) for result in results]

        return results

    def run_all_from_catalog(
        self,
        *,
        catalog_path: str | Path = "tests/catalog",
        validate_schema: bool = True,
        timeout_ms: int | None = None,
        run_id: str | None = None,
        log_path: str | Path | None = None,
    ) -> list[dict[str, Any]]:
        """Carga tests del catálogo y los ejecuta en orden."""
        return self.run_all(
            None,
            catalog_path=catalog_path,
            validate_schema=validate_schema,
            timeout_ms=timeout_ms,
            run_id=run_id,
            log_path=log_path,
        )

    def get_last_run_metrics(self) -> dict[str, Any]:
        """Devuelve métricas del último `run_all` ejecutado."""
        return dict(self.last_run_metrics)

    @staticmethod
    def _to_test_run_record(result: dict[str, Any]) -> dict[str, Any]:
        return {
            "test_id": str(result.get("test_id", "")),
            "version": str(result.get("test_version", "")),
            "status": str(result.get("status", "")),
            "duration_ms": int(result.get("runner_duration_ms", result.get("duration_ms", 0)) or 0),
            "error_summary": str(result.get("error_summary", "")),
        }

    def build_test_runs_payload(
        self,
        *,
        results: list[dict[str, Any]] | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Construye payload serializable para `test_runs.json`."""
        source = results if results is not None else self.last_results
        records = [self._to_test_run_record(result) for result in source]
        return {
            "generated_at_utc": self._utc_timestamp_iso(),
            "run_id": run_id or "",
            "test_runs": records,
        }

    def write_test_runs_json(
        self,
        *,
        output_path: str | Path | None = None,
        run_id: str | None = None,
        results: list[dict[str, Any]] | None = None,
    ) -> Path:
        """Persistencia de `test_runs.json` con esquema estable por test."""
        if output_path is None:
            if not run_id:
                raise ValueError("run_id es obligatorio cuando output_path no se informa")
            output = ruta_run(run_id) / "test_runs.json"
        else:
            output = Path(output_path)

        payload = self.build_test_runs_payload(results=results, run_id=run_id)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return output
