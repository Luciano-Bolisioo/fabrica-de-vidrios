"""Agente LangGraph de documentos (memoria por thread_id)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.agents.checkpointer import get_checkpointer
from app.agents.message_utils import last_ai_reply, public_history_from_messages, thread_config
from app.agents.prompts import DOCUMENTS_SYSTEM
from app.config import get_settings
from app.services import okf_store


@tool
def list_documents() -> dict[str, Any]:
    """Lista los documentos cargados (título, id, tags)."""
    return {"documents": okf_store.list_documents()}


@tool
def read_document(doc_id_or_title: str) -> dict[str, Any]:
    """Lee el contenido completo de un documento por id o título."""
    return okf_store.read_document(doc_id_or_title)


@tool
def search_documents(query: str) -> dict[str, Any]:
    """Busca en los documentos cargados por título, tags o contenido."""
    return okf_store.search_documents(query)


@tool
def list_related(doc_id: str) -> dict[str, Any]:
    """Lista documentos relacionados a uno dado."""
    return okf_store.list_related(doc_id)


TOOLS = [list_documents, read_document, search_documents, list_related]


def _build_llm() -> ChatOpenAI:
    settings = get_settings()
    if not settings.deepseek_api_key:
        raise RuntimeError(
            "Falta DEEPSEEK_API_KEY en el archivo .env. Copiá .env.example a .env y pegá tu clave."
        )
    return ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0.2,
    )


@lru_cache
def get_documents_agent():
    # prompt version: formal-v1
    return create_react_agent(
        _build_llm(),
        TOOLS,
        prompt=DOCUMENTS_SYSTEM,
        checkpointer=get_checkpointer(),
    )


def run_documents_chat(message: str, thread_id: str) -> str:
    agent = get_documents_agent()
    # Recordatorio por turno: evita respuestas viejas del hilo tipo "no hay documentos".
    enriched = (
        f"{message}\n\n"
        "(Antes de responder: liste o busque en los documentos cargados con las herramientas. "
        "No diga que no hay documentos sin listarlos en este turno.)"
    )
    result = agent.invoke(
        {"messages": [HumanMessage(content=enriched)]},
        config=thread_config(thread_id),
    )
    reply = last_ai_reply(result.get("messages") or [])
    return reply or "No pude armar una respuesta con los documentos cargados."


def get_documents_history(thread_id: str) -> list[dict[str, str]]:
    agent = get_documents_agent()
    state = agent.get_state(thread_config(thread_id))
    messages = (state.values or {}).get("messages") or []
    return public_history_from_messages(messages)
