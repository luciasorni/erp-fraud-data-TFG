"""Validación rápida de esquemas/config usados por AG03-05."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys

import yaml


def _fail(msg: str) -> None:
    raise ValueError(msg)


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        _fail(f"Falta fichero YAML: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        _fail(f"{path}: el YAML debe contener un objeto raíz")
    return payload


def _validate_tools_registry() -> None:
    payload = _load_yaml(Path("config/tools_registry.yaml"))
    tools = payload.get("tools")
    if not isinstance(tools, dict) or not tools:
        _fail("config/tools_registry.yaml: falta objeto 'tools'")
    required = {"DuckDBQuery", "Schema", "TestCatalog", "KBSearch", "RunStore"}
    missing = required.difference(set(tools.keys()))
    if missing:
        _fail(f"tools_registry incompleto, faltan: {sorted(missing)}")


def _validate_agent_policies() -> None:
    payload = _load_yaml(Path("config/agent_policies.yaml"))
    agents = payload.get("agents")
    if not isinstance(agents, dict) or not agents:
        _fail("config/agent_policies.yaml: falta objeto 'agents'")


def _validate_query_templates() -> None:
    payload = _load_yaml(Path("config/query_templates.yaml"))
    templates = payload.get("templates")
    if not isinstance(templates, dict) or not templates:
        _fail("config/query_templates.yaml: falta objeto 'templates'")
    for template_id, spec in templates.items():
        if not isinstance(spec, dict):
            _fail(f"{template_id}: especificación inválida")
        if not isinstance(spec.get("sql"), str) or not spec.get("sql", "").strip():
            _fail(f"{template_id}: falta sql")
        params = spec.get("required_params")
        if not isinstance(params, list) or not params:
            _fail(f"{template_id}: required_params inválido")


def _validate_catalog_yaml() -> None:
    catalog_dir = Path("tests/catalog")
    files = sorted(catalog_dir.glob("*.y*ml"))
    if not files:
        _fail("tests/catalog sin YAMLs")
    for path in files:
        payload = _load_yaml(path)
        for field in (
            "id",
            "version",
            "fraud_type",
            "red_flag_id",
            "process_step",
            "expected_output",
            "evidence_columns",
        ):
            if field not in payload:
                _fail(f"{path}: falta campo requerido '{field}'")


def _validate_red_flags_mapping() -> None:
    path = Path("config/red_flags_mapping.yaml")
    payload = _load_yaml(path)

    red_flags = payload.get("red_flags")
    if not isinstance(red_flags, list) or not red_flags:
        _fail(f"{path}: falta lista 'red_flags' no vacía")

    seen_ids: set[str] = set()
    for idx, item in enumerate(red_flags):
        if not isinstance(item, dict):
            _fail(f"{path}: red_flags[{idx}] debe ser objeto")
        red_flag_id = str(item.get("red_flag_id", "")).strip()
        fraud_type = str(item.get("fraud_type", "")).strip()
        name = str(item.get("name", "")).strip()
        description = str(item.get("description", "")).strip()
        if not red_flag_id:
            _fail(f"{path}: red_flags[{idx}] sin red_flag_id")
        if red_flag_id in seen_ids:
            _fail(f"{path}: red_flag_id duplicado '{red_flag_id}'")
        seen_ids.add(red_flag_id)
        if not re.match(r"^RF-[A-Z0-9-]+$", red_flag_id):
            _fail(f"{path}: red_flag_id inválido '{red_flag_id}'")
        if not name:
            _fail(f"{path}: {red_flag_id} sin name")
        if not description:
            _fail(f"{path}: {red_flag_id} sin description")
        if not fraud_type:
            _fail(f"{path}: {red_flag_id} sin fraud_type")


def _validate_prompt_naming() -> None:
    prompts_dir = Path("prompts")
    if not prompts_dir.exists():
        _fail("Falta carpeta prompts/")
    files = sorted(prompts_dir.glob("*.md"))
    if not files:
        _fail("prompts/ sin ficheros .md")
    pattern = re.compile(r"^[a-z_]+__v\d{3}\.md$")
    allowed_entrypoints = {
        "hypothesis_planner.md",
        "test_planner.md",
        "explainer.md",
        "scoring.md",
    }
    for path in files:
        if path.name == "README.md":
            continue
        if path.name in allowed_entrypoints:
            continue
        if not pattern.match(path.name):
            _fail(f"Nombre de prompt inválido: {path.name}")


def _validate_prompt_registry() -> None:
    path = Path("config/prompt_versions.yaml")
    payload = _load_yaml(path)
    nodes = payload.get("nodes")
    if not isinstance(nodes, dict) or not nodes:
        _fail(f"{path}: falta objeto 'nodes' no vacío")
    for node_id, entry in nodes.items():
        if not isinstance(entry, dict):
            _fail(f"{path}: nodes.{node_id} debe ser objeto")
        prompt_file = str(entry.get("file", "")).strip()
        version = str(entry.get("version", "")).strip()
        if not prompt_file:
            _fail(f"{path}: nodes.{node_id}.file vacío")
        if not version:
            _fail(f"{path}: nodes.{node_id}.version vacío")
        file_path = Path(prompt_file)
        if not file_path.exists():
            _fail(f"{path}: prompt file no existe: {prompt_file}")


def _validate_data_dictionary_json() -> None:
    path = Path("data_dictionary.json")
    if not path.exists():
        return
    raw = path.read_text(encoding="utf-8")
    json.loads(raw)


def _validate_env_example() -> None:
    path = Path(".env.example")
    if not path.exists():
        _fail("Falta .env.example")
    text = path.read_text(encoding="utf-8")
    required_keys = (
        "LANGSMITH_API_KEY",
        "OPENAI_API_KEY",
        "RUN_MODE",
        "S3_INPUT_URI",
        "S3_OUTPUT_URI",
        "S3_STATE_URI",
        "PROCESS_SCOPE",
        "LANGSMITH_TRACING",
        "LANGSMITH_PROJECT",
        "AWS_REGION",
    )
    for key in required_keys:
        if key not in text:
            _fail(f".env.example: falta clave {key}")


def _validate_models_config() -> None:
    path = Path("config/models.yaml")
    payload = _load_yaml(path)
    scoring = payload.get("scoring")
    if not isinstance(scoring, dict):
        _fail(f"{path}: falta objeto 'scoring'")
    profiles = scoring.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        _fail(f"{path}: falta objeto 'scoring.profiles' no vacío")
    graph_nodes = payload.get("graph_nodes")
    if not isinstance(graph_nodes, dict) or not graph_nodes:
        _fail(f"{path}: falta objeto 'graph_nodes' no vacío")


def main() -> int:
    try:
        _validate_tools_registry()
        _validate_agent_policies()
        _validate_query_templates()
        _validate_catalog_yaml()
        _validate_red_flags_mapping()
        _validate_prompt_naming()
        _validate_prompt_registry()
        _validate_models_config()
        _validate_data_dictionary_json()
        _validate_env_example()
    except Exception as exc:
        print(f"ERROR schema/config validation: {exc}", file=sys.stderr)
        return 1
    print("OK schema/config validation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
