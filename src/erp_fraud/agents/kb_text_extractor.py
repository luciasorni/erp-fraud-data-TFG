"""Extracción y normalización de texto para KB (RF15e-02)."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable


class KBTextExtractionError(ValueError):
    """Error de extracción/normalización de texto KB."""


@dataclass(frozen=True)
class ExtractedTextDocument:
    source_id: str
    source_path: str
    doc_type: str
    section_id: str
    text: str
    text_hash: str
    metadata: dict[str, object]


def normalize_text(text: str) -> str:
    """Normaliza texto para indexado reproducible."""
    if not isinstance(text, str):
        raise TypeError("text debe ser string")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\u00a0", " ")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_text_from_pdf(
    *,
    source_id: str,
    path: str | Path,
) -> list[ExtractedTextDocument]:
    """Extrae texto por página desde PDF."""
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"No existe PDF: {resolved}")

    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Falta dependencia pypdf para extraer texto de PDF") from exc

    reader = PdfReader(str(resolved))
    out: list[ExtractedTextDocument] = []
    for idx, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        text = normalize_text(raw)
        out.append(
            ExtractedTextDocument(
                source_id=source_id,
                source_path=str(resolved),
                doc_type="pdf",
                section_id=f"page_{idx:04d}",
                text=text,
                text_hash=_text_hash(text),
                metadata={
                    "source": str(resolved),
                    "page": idx,
                },
            )
        )
    return out


def extract_text_from_markdown_or_text(
    *,
    source_id: str,
    path: str | Path,
) -> list[ExtractedTextDocument]:
    """Extrae y normaliza texto de md/txt (1 sección por fichero)."""
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"No existe fichero de texto: {resolved}")

    raw = resolved.read_text(encoding="utf-8")
    text = normalize_text(raw)
    section_id = "full_document"
    return [
        ExtractedTextDocument(
            source_id=source_id,
            source_path=str(resolved),
            doc_type=resolved.suffix.lower().lstrip("."),
            section_id=section_id,
            text=text,
            text_hash=_text_hash(text),
            metadata={
                "source": str(resolved),
                "section": section_id,
            },
        )
    ]


def extract_text_from_structured_file(
    *,
    source_id: str,
    path: str | Path,
) -> list[ExtractedTextDocument]:
    """Extrae texto normalizado de JSON/YAML serializando a JSON estable."""
    resolved = Path(path)
    if not resolved.exists():
        raise FileNotFoundError(f"No existe fichero estructurado: {resolved}")

    suffix = resolved.suffix.lower()
    raw = resolved.read_text(encoding="utf-8")

    if suffix == ".json":
        payload = json.loads(raw)
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("No se puede leer YAML sin PyYAML instalado") from exc
        payload = yaml.safe_load(raw)
    else:
        raise KBTextExtractionError(f"Formato estructurado no soportado: {resolved}")

    stable_text = normalize_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))
    section_id = "full_document"
    return [
        ExtractedTextDocument(
            source_id=source_id,
            source_path=str(resolved),
            doc_type=resolved.suffix.lower().lstrip("."),
            section_id=section_id,
            text=stable_text,
            text_hash=_text_hash(stable_text),
            metadata={
                "source": str(resolved),
                "section": section_id,
            },
        )
    ]


def extract_text_from_path(
    *,
    source_id: str,
    path: str | Path,
) -> list[ExtractedTextDocument]:
    """Despacha extractor según extensión."""
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(source_id=source_id, path=path)
    if suffix in {".md", ".txt"}:
        return extract_text_from_markdown_or_text(source_id=source_id, path=path)
    if suffix in {".json", ".yaml", ".yml"}:
        return extract_text_from_structured_file(source_id=source_id, path=path)
    raise KBTextExtractionError(f"Formato no soportado para extracción KB: {path}")


def save_normalized_text_documents(
    *,
    documents: Iterable[ExtractedTextDocument],
    output_dir: str | Path,
) -> dict[str, str]:
    """Guarda texto normalizado en JSONL y TXT agregado."""
    resolved_out = Path(output_dir)
    resolved_out.mkdir(parents=True, exist_ok=True)

    jsonl_path = resolved_out / "normalized_documents.jsonl"
    txt_path = resolved_out / "normalized_corpus.txt"

    docs = list(documents)
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for doc in docs:
            fh.write(json.dumps(asdict(doc), ensure_ascii=False, sort_keys=True) + "\n")

    with txt_path.open("w", encoding="utf-8") as fh:
        for idx, doc in enumerate(docs, start=1):
            fh.write(f"### DOC {idx} | {doc.source_id} | {doc.section_id}\n")
            fh.write(doc.text)
            fh.write("\n\n")

    return {
        "jsonl": str(jsonl_path),
        "txt": str(txt_path),
    }
