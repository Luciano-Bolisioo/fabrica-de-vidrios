"""Ingesta de PDFs: MarkItDown → documento OKF local."""

from __future__ import annotations

import re
from pathlib import Path

from markitdown import MarkItDown

from app.config import get_settings
from app.services import okf_store


def _guess_title(filename: str, markdown: str) -> str:
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()[:120]
    stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
    return stem.title() or "Documento"


def _guess_tags(title: str, markdown: str) -> list[str]:
    text = f"{title}\n{markdown[:3000]}".lower()
    candidates = [
        ("cliente", "clientes"),
        ("clientes", "clientes"),
        ("venta", "ventas"),
        ("ventas", "ventas"),
        ("precio", "precios"),
        ("precios", "precios"),
        ("factura", "facturas"),
        ("presupuesto", "presupuestos"),
        ("vidrio", "vidrios"),
        ("laminado", "laminado"),
        ("templado", "templado"),
        ("contrato", "contratos"),
    ]
    tags: list[str] = []
    for needle, tag in candidates:
        if needle in text and tag not in tags:
            tags.append(tag)
    if not tags:
        tags.append("general")
    return tags[:8]


def ingest_pdf(file_bytes: bytes, filename: str) -> dict:
    settings = get_settings()
    safe_name = re.sub(r"[^\w.\-]+", "_", filename) or "documento.pdf"
    if not safe_name.lower().endswith(".pdf"):
        safe_name += ".pdf"

    dest = settings.uploads_dir / safe_name
    # evitar overwrite silencioso
    if dest.exists():
        stem = dest.stem
        dest = settings.uploads_dir / f"{stem}_{len(list(settings.uploads_dir.glob('*')))}{dest.suffix}"

    dest.write_bytes(file_bytes)

    md = MarkItDown()
    result = md.convert(str(dest))
    markdown = (result.text_content or "").strip()
    if not markdown:
        markdown = "_No se pudo extraer texto de este archivo._"

    title = _guess_title(filename, markdown)
    tags = _guess_tags(title, markdown)
    meta = okf_store.save_document(
        title=title,
        body=markdown,
        source=dest.name,
        tags=tags,
    )
    return {
        "id": meta["id"],
        "title": meta["title"],
        "tags": meta.get("tags") or [],
        "source": meta.get("source") or "",
        "message": f"Listo, cargué '{meta['title']}' y ya podés preguntarme sobre ese archivo.",
    }
