API_BASE_URL = "http://localhost:8000/api/v1"
APP_TITLE = "ERP Fraud Analysis Workbench"
APP_SUBTITLE = "Backend cloud multiagente para análisis antifraude ERP sobre P2P y O2C."

PAGE_ICON = "app/ui/assets/logo_placeholder.png"

SCOPE_OPTIONS = ["p2p", "o2c", "both"]
SCOPE_LABELS = {
    "p2p": "P2P",
    "o2c": "O2C",
    "both": "P2P + O2C",
}

LLM_OPTIONS = ["real", "stub"]
PIPELINE_OPTIONS = ["graph"]

STATUS_COLORS = {
    "COMPLETED": "#0F766E",
    "RUNNING": "#C97A10",
    "FAILED": "#B42318",
    "SUBMITTED": "#155EEF",
    "OK": "#0F766E",
    "OK_WITH_WARNINGS": "#C97A10",
    "ABORTED": "#B42318",
    "UNKNOWN": "#667085",
}

STATUS_LABELS = {
    "COMPLETED": "Completada",
    "RUNNING": "En curso",
    "FAILED": "Fallida",
    "SUBMITTED": "En cola",
    "OK": "OK",
    "OK_WITH_WARNINGS": "Con avisos",
    "ABORTED": "Abortada",
    "UNKNOWN": "Desconocido",
}

DEFAULT_RUN_FILTERS = {
    "dataset": "Todos",
    "scope": "Todos",
    "status": "Todos",
    "date_from": None,
}

ALLOWED_DRILLDOWN_ACTIONS = ["finding_rows"]

