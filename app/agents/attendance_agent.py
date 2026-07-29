"""Agente LangGraph de asistencias (memoria por thread_id)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.agents.checkpointer import get_checkpointer
from app.agents.message_utils import last_ai_reply, public_history_from_messages, thread_config
from app.agents.prompts import ATTENDANCE_SYSTEM
from app.config import get_settings
from app.services import sheets


@tool
def list_employees() -> dict[str, Any]:
    """Lista empleados, sectores y el período de la planilla de asistencias."""
    return sheets.list_employees_tool()


@tool
def get_attendance(
    employee_query: str,
    day_from: int | None = None,
    day_to: int | None = None,
) -> dict[str, Any]:
    """Devuelve las fichadas día por día de un empleado. employee_query puede ser nombre o ID."""
    return sheets.get_attendance_tool(employee_query, day_from, day_to)


@tool
def calculate_hours(
    employee_query: str,
    day_from: int | None = None,
    day_to: int | None = None,
) -> dict[str, Any]:
    """Calcula horas trabajadas, extras y faltantes de un empleado (opcionalmente por rango de días)."""
    return sheets.calculate_hours_tool(employee_query, day_from, day_to)


@tool
def summarize_department(department: str) -> dict[str, Any]:
    """Resume asistencia y horas de un sector: Administracion, Ventas, Produccion o Maestranza."""
    return sheets.summarize_department_tool(department)


@tool
def refresh_sheet() -> dict[str, Any]:
    """Vuelve a leer la planilla de asistencias para traer datos actualizados."""
    return sheets.refresh_sheet_tool()


TOOLS = [list_employees, get_attendance, calculate_hours, summarize_department, refresh_sheet]


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
def get_attendance_agent():
    # prompt version: formal-v1
    return create_react_agent(
        _build_llm(),
        TOOLS,
        prompt=ATTENDANCE_SYSTEM,
        checkpointer=get_checkpointer(),
    )


def run_attendance_chat(message: str, thread_id: str) -> str:
    agent = get_attendance_agent()
    result = agent.invoke(
        {"messages": [HumanMessage(content=message)]},
        config=thread_config(thread_id),
    )
    reply = last_ai_reply(result.get("messages") or [])
    return reply or "No pude armar una respuesta con la planilla."


def get_attendance_history(thread_id: str) -> list[dict[str, str]]:
    agent = get_attendance_agent()
    state = agent.get_state(thread_config(thread_id))
    messages = (state.values or {}).get("messages") or []
    return public_history_from_messages(messages)
