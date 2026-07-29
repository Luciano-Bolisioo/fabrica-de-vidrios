"""Clasificador de intención: asistencias vs documentos."""

from __future__ import annotations

import logging
import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)

Intent = Literal["asistencias", "documentos"]

_ATT_KEYWORDS = re.compile(
    r"\b("
    r"asistencia|asistencias|fichada|fichadas|horas?\s*trabaj|empleado|empleados|"
    r"lleg[oó]|tarde|sector|producci[oó]n|administraci[oó]n|ventas|maestranza|"
    r"planilla|extra|faltante|presentismo|entrada|salida"
    r")\b",
    re.I,
)

_DOC_KEYWORDS = re.compile(
    r"\b("
    r"cliente|clientes|precio|precios|presupuesto|venta|ventas|pdf|documento|"
    r"cristaler[ií]a|laminado|templado|dvh|factura|descuento|pago|obra|"
    r"belgrano|vidrios?\s+del\s+sur"
    r")\b",
    re.I,
)

_CLASSIFY_SYSTEM = """\
Clasifique la consulta del usuario en UNA sola etiqueta:
- asistencias: fichadas, horas trabajadas, empleados, sectores, llegadas tarde, planilla de personal
- documentos: clientes, precios, ventas, presupuestos, archivos PDF, productos de vidrio, condiciones comerciales

Responda SOLO con una palabra: asistencias o documentos.
"""


def _heuristic(message: str) -> Intent:
    text = message or ""
    att = bool(_ATT_KEYWORDS.search(text))
    doc = bool(_DOC_KEYWORDS.search(text))
    if att and not doc:
        return "asistencias"
    if doc and not att:
        return "documentos"
    if att and doc:
        # Priorizar documentos si habla de cliente/precio concreto
        if re.search(r"cliente|precio|presupuesto|cristaler", text, re.I):
            return "documentos"
        return "asistencias"
    return "documentos"


def classify_intent(message: str) -> Intent:
    """Devuelve 'asistencias' o 'documentos'."""
    text = (message or "").strip()
    if not text:
        return "asistencias"

    settings = get_settings()
    if not settings.deepseek_api_key:
        return _heuristic(text)

    try:
        llm = ChatOpenAI(
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            temperature=0,
        )
        result = llm.invoke(
            [
                SystemMessage(content=_CLASSIFY_SYSTEM),
                HumanMessage(content=text),
            ]
        )
        raw = (result.content or "").strip().lower()
        if isinstance(raw, list):
            raw = " ".join(str(x) for x in raw).lower()
        if "asistencia" in raw:
            return "asistencias"
        if "documento" in raw:
            return "documentos"
        logger.warning("Clasificador devolvió respuesta rara: %r — uso heurística", raw)
    except Exception:  # noqa: BLE001
        logger.exception("Falló classify_intent — uso heurística")

    return _heuristic(text)
