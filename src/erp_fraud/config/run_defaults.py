"""Defaults compartidos entre CLI y nodos de grafo (RF14b-P02)."""

DEFAULT_RUN_INPUT_ZIP = "erp_fraud_data.zip"
DEFAULT_OUT_DIR = "run_results"
DEFAULT_DB_PATH = "erp.duckdb"
DEFAULT_SCHEMA_NAME = "main"
DEFAULT_TABLE_NAME = "fraud_1"
DEFAULT_CATALOG_PATH = "tests/catalog"
DEFAULT_WEIGHTS_CONFIG = "config/weights.yaml"
DEFAULT_SAMPLE_TOP_N = 20
DEFAULT_PROCESS_FAMILY = "p2p"
DEFAULT_O2C_CANONICAL_SCHEMA_CONFIG = "config/canonical_schema_o2c.yaml"
DEFAULT_O2C_IDENTITY_CONFIG = "config/o2c_entity_identity.yaml"
DEFAULT_O2C_MAPPING_CONFIG = "config/column_mapping_o2c.yaml"
DEFAULT_O2C_TARGET_SCHEMA = "o2c"

DEFAULT_AWS_REGION = "eu-west-1"
DEFAULT_RUN_MODE = "local"
DEFAULT_S3_INPUT_URI = "s3://tfg-fraud-dev-euw1-lucia01/inputs/"
DEFAULT_S3_OUTPUT_URI = "s3://tfg-fraud-dev-euw1-lucia01/runs/"
DEFAULT_S3_STATE_URI = "s3://tfg-fraud-dev-euw1-lucia01/state/"
DEFAULT_PROCESS_SCOPE = "p2p"
DEFAULT_LANGSMITH_TRACING = False
DEFAULT_LANGSMITH_PROJECT = "erp-fraud-tfg"

DEFAULT_KB_ENABLED = True
DEFAULT_KB_SOURCES_CONFIG = "config/kb_sources.yaml"
DEFAULT_KB_CHUNKING_CONFIG = "config/kb_chunking.yaml"
DEFAULT_KB_CHROMA_CONFIG = "config/kb_chroma.yaml"
DEFAULT_KB_MANIFEST_PATH = "kb/index_manifest.json"
DEFAULT_KB_STATE_PATH = "kb/index_state.json"

DEFAULT_BASE_DIR = "."
DEFAULT_HYPOTHESIS_KB_TOP_K = 3
DEFAULT_HYPOTHESIS_MAX_ITEMS = 3
DEFAULT_TEST_PLANNER_TOP_N = 2
DEFAULT_EXECUTOR_TIMEOUT_MS = 10000
DEFAULT_EXPLAINER_KB_TOP_K = 2
DEFAULT_EXPLAINER_TOP_K = 5
DEFAULT_SCORING_TOP_K = 20
