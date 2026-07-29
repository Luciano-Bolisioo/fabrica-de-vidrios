"""Helpers compartidos para agentes con checkpointer."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage


def message_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts).strip()
    return str(content).strip()


def last_ai_reply(messages: list[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and message_text(msg.content) and not getattr(msg, "tool_calls", None):
            return message_text(msg.content)
    return ""


def thread_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def public_history_from_messages(messages: list[BaseMessage]) -> list[dict[str, str]]:
    """Solo user/assistant visibles (sin tools)."""
    history: list[dict[str, str]] = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            continue
        if isinstance(msg, HumanMessage):
            text = message_text(msg.content)
            # Quitar recordatorio interno del agente de documentos
            marker = "\n\n(Antes de responder:"
            if marker in text:
                text = text.split(marker, 1)[0].strip()
            if text:
                history.append({"role": "user", "content": text})
        elif isinstance(msg, AIMessage):
            # saltar mensajes intermedios que solo disparan tools
            if getattr(msg, "tool_calls", None):
                continue
            text = message_text(msg.content)
            if text:
                history.append({"role": "assistant", "content": text})
    return history
