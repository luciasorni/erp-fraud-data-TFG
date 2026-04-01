PYTHON ?= /opt/anaconda3/bin/python
CLI := $(PYTHON) -m src.erp_fraud.cli.main
PYTEST := $(PYTHON) -m pytest -q

INPUT_ZIP ?= erp_fraud_data.zip
RUN_ID ?=
OUT_DIR ?= run_results
CONFIG ?=
SELECT_TESTS ?=
TOP_K ?=

.PHONY: help run test pre-langsmith-gate test-rf01 test-rf02 test-rf02b test-rf03 test-rf04 test-rf05 test-rf06 test-rf07 test-rf08

help:
	@echo "Targets disponibles:"
	@echo "  make run            # Ejecuta pipeline completo RF10 (usa INPUT_ZIP/OUT_DIR/RUN_ID)"
	@echo "  make test           # Ejecuta test suite de requisitos implementados"
	@echo "  make pre-langsmith-gate  # Ejecuta gate previo RF14b (contratos + regresión crítica)"
	@echo "  make test-rf08      # Ejecuta solo tests de reporte RF08"
	@echo ""
	@echo "Variables opcionales:"
	@echo "  PYTHON=/ruta/python"
	@echo "  INPUT_ZIP=erp_fraud_data.zip"
	@echo "  OUT_DIR=run_results"
	@echo "  RUN_ID=mi-run"
	@echo "  CONFIG=config/run_config.yaml"
	@echo "  SELECT_TESTS=TST-DUPLICATE-POSTINGS,TST-UNUSUAL-AMOUNT-BY-VENDOR"
	@echo "  TOP_K=20"

run:
	$(CLI) run \
		--input-zip $(INPUT_ZIP) \
		$(if $(RUN_ID),--run-id $(RUN_ID),) \
		--out-dir $(OUT_DIR) \
		$(if $(CONFIG),--config $(CONFIG),) \
		$(if $(SELECT_TESTS),--select-tests $(SELECT_TESTS),) \
		$(if $(TOP_K),--top-k $(TOP_K),)

test:
	$(PYTEST) \
		tests/test_rf01_ingest_storage.py \
		tests/test_rf02_data_dictionary.py \
		tests/test_rf02b_data_validation.py \
		tests/test_rf03_catalog.py \
		tests/test_rf04_runner.py \
		tests/test_rf05_result_schema_and_writer.py \
		tests/test_rf06_drilldown.py \
		tests/test_rf06_drilldown_components.py \
		tests/test_rf07_ranking.py \
		tests/test_rf08_reporting.py

pre-langsmith-gate:
	$(PYTHON) scripts/run_pre_langsmith_gate.py

test-rf01:
	$(PYTEST) tests/test_rf01_ingest_storage.py

test-rf02:
	$(PYTEST) tests/test_rf02_data_dictionary.py

test-rf02b:
	$(PYTEST) tests/test_rf02b_data_validation.py

test-rf03:
	$(PYTEST) tests/test_rf03_catalog.py

test-rf04:
	$(PYTEST) tests/test_rf04_runner.py

test-rf05:
	$(PYTEST) tests/test_rf05_result_schema_and_writer.py

test-rf06:
	$(PYTEST) tests/test_rf06_drilldown.py tests/test_rf06_drilldown_components.py

test-rf07:
	$(PYTEST) tests/test_rf07_ranking.py

test-rf08:
	$(PYTEST) tests/test_rf08_reporting.py
