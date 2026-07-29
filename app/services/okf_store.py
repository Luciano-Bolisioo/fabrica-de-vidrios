"""Almacén local de documentos en formato OKF (markdown + frontmatter)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.config import get_settings


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = (
        text.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ñ", "n")
    )
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:80] or "documento"


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2].lstrip("\n")
            return meta, body
    return {}, content


def _write_doc(path: Path, meta: dict[str, Any], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    front = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip()
    path.write_text(f"---\n{front}\n---\n\n{body.rstrip()}\n", encoding="utf-8")


def rebuild_index() -> None:
    settings = get_settings()
    docs = list_documents()
    lines = [
        "---",
        "id: index",
        "title: Catálogo de documentos",
        "type: index",
        "---",
        "",
        "# Catálogo de documentos",
        "",
    ]
    if not docs:
        lines.append("_No hay documentos cargados todavía._")
    else:
        for doc in docs:
            tags = ", ".join(doc.get("tags") or []) or "sin tags"
            lines.append(
                f"- [{doc['title']}](documents/{doc['id']}.md) — tags: {tags}"
            )
    (settings.okf_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_document(
    title: str,
    body: str,
    *,
    source: str = "",
    tags: list[str] | None = None,
    doc_id: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    doc_id = doc_id or _slugify(title)
    path = settings.okf_documents_dir / f"{doc_id}.md"
    # evitar colisiones
    if path.exists() and doc_id == _slugify(title):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        doc_id = f"{doc_id}-{stamp}"
        path = settings.okf_documents_dir / f"{doc_id}.md"

    meta = {
        "id": doc_id,
        "title": title,
        "tags": tags or [],
        "source": source,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "related": [],
    }
    _write_doc(path, meta, body)
    rebuild_index()
    return meta


def list_documents() -> list[dict[str, Any]]:
    settings = get_settings()
    docs: list[dict[str, Any]] = []
    for path in sorted(settings.okf_documents_dir.glob("*.md")):
        meta, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
        docs.append(
            {
                "id": meta.get("id") or path.stem,
                "title": meta.get("title") or path.stem,
                "tags": meta.get("tags") or [],
                "source": meta.get("source") or "",
                "created_at": meta.get("created_at") or "",
            }
        )
    return docs


def delete_document(doc_id: str) -> dict[str, Any]:
    """Borra el markdown OKF y el PDF fuente si existe. Devuelve meta o error."""
    settings = get_settings()
    q = (doc_id or "").strip()
    if not q:
        return {"error": "Falta el id del documento."}

    target: Path | None = None
    meta: dict[str, Any] = {}
    for path in settings.okf_documents_dir.glob("*.md"):
        parsed, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
        stem_id = str(parsed.get("id") or path.stem)
        if stem_id == q or path.stem == q:
            target = path
            meta = parsed
            break

    if target is None:
        return {"error": f"No encontré el documento '{q}'."}

    source_name = str(meta.get("source") or "").strip()
    title = str(meta.get("title") or target.stem)
    resolved_id = str(meta.get("id") or target.stem)

    target.unlink(missing_ok=True)

    if source_name:
        upload = settings.uploads_dir / Path(source_name).name
        if upload.is_file():
            upload.unlink(missing_ok=True)

    # Quitar referencias related en otros docs
    for path in settings.okf_documents_dir.glob("*.md"):
        other_meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        related = list(other_meta.get("related") or [])
        if resolved_id not in related:
            continue
        other_meta["related"] = [r for r in related if r != resolved_id]
        _write_doc(path, other_meta, body)

    rebuild_index()
    return {"id": resolved_id, "title": title, "deleted": True}


def read_document(doc_id_or_title: str) -> dict[str, Any]:
    settings = get_settings()
    q = (doc_id_or_title or "").strip().lower()
    if not q:
        return {"error": "No me dijiste qué documento leer."}

    # by id / filename
    candidates = list(settings.okf_documents_dir.glob("*.md"))
    for path in candidates:
        meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        doc_id = str(meta.get("id") or path.stem).lower()
        title = str(meta.get("title") or "").lower()
        if q == doc_id or q == title or q in title or q in doc_id:
            return {
                "id": meta.get("id") or path.stem,
                "title": meta.get("title") or path.stem,
                "tags": meta.get("tags") or [],
                "source": meta.get("source") or "",
                "related": meta.get("related") or [],
                "content": body,
            }
    return {"error": f"No encontré el documento '{doc_id_or_title}'."}


def search_documents(query: str, limit: int = 8) -> dict[str, Any]:
    settings = get_settings()
    q = (query or "").strip().lower()
    if not q:
        return {"results": list_documents()[:limit]}

    results: list[dict[str, Any]] = []
    for path in settings.okf_documents_dir.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(text)
        hay = " ".join(
            [
                str(meta.get("id", "")),
                str(meta.get("title", "")),
                " ".join(meta.get("tags") or []),
                body,
            ]
        ).lower()
        score = 0
        for token in q.split():
            if token in hay:
                score += hay.count(token)
        if score > 0 or q in hay:
            snippet = body[:400].replace("\n", " ")
            results.append(
                {
                    "id": meta.get("id") or path.stem,
                    "title": meta.get("title") or path.stem,
                    "tags": meta.get("tags") or [],
                    "score": score or 1,
                    "snippet": snippet,
                }
            )
    results.sort(key=lambda r: r["score"], reverse=True)
    return {"query": query, "results": results[:limit]}


def list_related(doc_id: str) -> dict[str, Any]:
    doc = read_document(doc_id)
    if "error" in doc:
        return doc
    related_ids = doc.get("related") or []
    related = []
    for rid in related_ids:
        related.append(read_document(str(rid)))
    return {"id": doc["id"], "title": doc["title"], "related": related}
