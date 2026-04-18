from __future__ import annotations

import ast
import json
from typing import Any

import streamlit as st


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, tuple, set, dict)) and len(value) == 0:
        return True
    return False


def _maybe_parse_structured_string(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return value

    looks_structured = (
        (text.startswith("{") and text.endswith("}"))
        or (text.startswith("[") and text.endswith("]"))
    )
    if not looks_structured:
        return value

    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(text)
        except Exception:
            pass

    return value


def _pretty(value: Any) -> str:
    value = _maybe_parse_structured_string(value)

    if isinstance(value, bool):
        return "Sí" if value else "No"
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    return json.dumps(value, ensure_ascii=False)


def _humanize_key(key: str) -> str:
    return key.replace("_", " ").capitalize()


def render_presentable_content(content: Any) -> None:
    content = _maybe_parse_structured_string(content)

    if _is_empty(content):
        st.write("-")
        return

    if isinstance(content, dict):
        preferred_order = [
            "overall_assessment",
            "conclusion",
            "summary",
            "risk_posture",
            "implication",
            "action",
            "procedure",
            "why",
            "rationale",
            "reason",
            "owner",
            "urgency",
            "priority",
            "severity",
            "test_id",
            "expected_value",
            "key_observations",
            "evidence",
            "expected_evidence",
            "key_evidence",
        ]
        used: set[str] = set()

        for key in preferred_order:
            if key not in content:
                continue
            value = _maybe_parse_structured_string(content[key])
            if _is_empty(value):
                continue

            st.markdown(f"**{_humanize_key(key)}:**")
            render_presentable_content(value)
            used.add(key)

        for key, value in content.items():
            if key in used:
                continue

            value = _maybe_parse_structured_string(value)
            if _is_empty(value):
                continue

            st.markdown(f"**{_humanize_key(key)}:**")
            render_presentable_content(value)
        return

    if isinstance(content, list):
        simple_items = []
        complex_items = []

        for item in content:
            parsed = _maybe_parse_structured_string(item)
            if isinstance(parsed, (dict, list)):
                complex_items.append(parsed)
            else:
                simple_items.append(parsed)

        for item in simple_items:
            st.markdown(f"- {_pretty(item)}")

        for item in complex_items:
            render_presentable_content(item)
        return

    st.write(_pretty(content))


def _title_for_item(item: dict[str, Any], default_title: str, idx: int) -> str:
    attrs = _clean_attributes_for_display(item.get("attributes"))
    for key in ("action", "procedure", "test_id", "conclusion", "title", "name"):
        value = _maybe_parse_structured_string(item.get(key))
        if isinstance(value, str) and value.strip():
            return value.strip()
        value = _maybe_parse_structured_string(attrs.get(key))
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"{default_title} {idx}"


def _subtitle_for_item(item: dict[str, Any]) -> str:
    attrs = _clean_attributes_for_display(item.get("attributes"))
    for key in ("why", "rationale", "reason", "overall_assessment", "summary"):
        value = _maybe_parse_structured_string(item.get(key))
        if isinstance(value, str) and value.strip():
            return value.strip()
        value = _maybe_parse_structured_string(attrs.get(key))
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _body_text_for_item(item: dict[str, Any], *, title: str, subtitle: str) -> str:
    attrs = _clean_attributes_for_display(item.get("attributes"))
    for key in ("summary", "why", "rationale", "reason", "overall_assessment"):
        value = _maybe_parse_structured_string(item.get(key))
        if not isinstance(value, str):
            value = _maybe_parse_structured_string(attrs.get(key))
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text:
            continue
        if text == title or text == subtitle:
            continue
        return text
    return ""


def _metadata_line(item: dict[str, Any]) -> str:
    attrs = _clean_attributes_for_display(item.get("attributes"))
    section = str(item.get("section") or attrs.get("section") or "").strip()
    title = str(item.get("title") or "").strip()
    parts: list[str] = []
    metadata_pairs = [
        ("Prioridad", "priority"),
        ("Urgencia", "urgency"),
        ("Severidad", "severity"),
        ("Responsable", "owner"),
        ("Origen", "source"),
    ]
    if section != "recommended_tests":
        metadata_pairs.append(("Test", "test_id"))

    for label, key in metadata_pairs:
        value = _maybe_parse_structured_string(item.get(key))
        if _is_empty(value):
            value = _maybe_parse_structured_string(attrs.get(key))
        if key == "test_id" and isinstance(value, str) and value.strip() == title:
            continue
        if not _is_empty(value):
            parts.append(f"**{label}:** {_pretty(value)}")
    return " · ".join(parts)


def _evidence_list(item: dict[str, Any]) -> list[Any]:
    attrs = _clean_attributes_for_display(item.get("attributes"))
    for key in ("evidence", "expected_evidence", "key_evidence"):
        value = _maybe_parse_structured_string(item.get(key))
        if _is_empty(value):
            value = _maybe_parse_structured_string(attrs.get(key))
        if isinstance(value, list) and value:
            return value
    return []


def _clean_attributes_for_display(value: Any) -> dict[str, Any]:
    attributes = _maybe_parse_structured_string(value)
    if not isinstance(attributes, dict):
        return {}
    hidden_keys = {"section", "id", "status", "title", "summary", "subtitle", "test_id"}
    cleaned: dict[str, Any] = {}
    for key, item in attributes.items():
        parsed = _maybe_parse_structured_string(item)
        if key in hidden_keys or _is_empty(parsed):
            continue
        cleaned[key] = parsed
    return cleaned


def _fallback_detail_text(*, item: dict[str, Any], body_text: str, evidence: list[Any], attributes: dict[str, Any]) -> str:
    if body_text or evidence or attributes:
        return ""
    section = str(item.get("section") or attributes.get("section") or "").strip()
    if section == "recommendations":
        return "Acción sugerida para reforzar la investigación del caso."
    if section == "recommended_tests":
        return "Test sugerido para ampliar el contraste y la cobertura de la hipótesis."
    if section == "audit_procedures":
        return "Procedimiento sugerido para validación manual o revisión auditora."
    return ""


def _render_compact_item(
    item: dict[str, Any],
    *,
    default_title: str,
    idx: int,
    expanded: bool = False,
) -> None:
    title = _title_for_item(item, default_title, idx)
    subtitle = _subtitle_for_item(item)
    body_text = _body_text_for_item(item, title=title, subtitle=subtitle)
    metadata = _metadata_line(item)
    evidence = _evidence_list(item)
    attributes = _clean_attributes_for_display(item.get("attributes"))
    fallback_detail = _fallback_detail_text(
        item=item,
        body_text=body_text,
        evidence=evidence,
        attributes=attributes,
    )

    with st.expander(title, expanded=expanded):
        if subtitle and subtitle != title and subtitle != body_text:
            st.caption(subtitle)

        if body_text:
            st.write(body_text)
        elif fallback_detail:
            st.write(fallback_detail)

        if metadata:
            st.markdown(metadata)

        if evidence:
            st.markdown("**Evidencia**")
            render_presentable_content(evidence)

        if attributes:
            st.markdown("**Contexto adicional**")
            render_presentable_content(attributes)

        hidden_keys = {
            "action",
            "procedure",
            "test_id",
            "conclusion",
            "title",
            "name",
            "summary",
            "overall_assessment",
            "why",
            "rationale",
            "reason",
            "priority",
            "urgency",
            "severity",
            "owner",
            "evidence",
            "expected_evidence",
            "key_evidence",
            "id",
            "subtitle",
            "status",
            "section",
            "attributes",
        }

        remaining = {}
        for key, value in item.items():
            if key in hidden_keys:
                continue
            value = _maybe_parse_structured_string(value)
            if _is_empty(value):
                continue
            remaining[key] = value

        if remaining:
            render_presentable_content(remaining)


def render_recommendations_panel(
    items: list[dict[str, Any]] | None,
    *,
    title: str,
    empty_message: str,
) -> None:
    if not items:
        st.info(empty_message)
        return

    normalized_items: list[Any] = [_maybe_parse_structured_string(item) for item in items]

    st.caption(f"{len(normalized_items)} elemento(s)")

    for idx, item in enumerate(normalized_items, start=1):
        if isinstance(item, dict):
            _render_compact_item(
                item,
                default_title=title[:-1] if title.endswith("s") else title,
                idx=idx,
                expanded=(idx == 1),
            )
        else:
            with st.expander(f"{title[:-1] if title.endswith('s') else title} {idx}", expanded=(idx == 1)):
                render_presentable_content(item)
