"""Bot de Telegram — preguntas a agentes de asistencias y documentos.

Uso:
  python -m app.telegram_bot

Habla con la API (API_BASE_URL): misma planilla y mismos PDFs que la UI.
Por defecto enruta solo (modo auto). /asistencias y /documentos fijan el modo;
/auto vuelve al enrutado automático.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Literal

import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.agents.router import classify_intent
from app.config import get_settings

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("telegram_bot")

_WAKE_TIMEOUT = 90.0
_CHAT_TIMEOUT = 180.0
_UPLOAD_TIMEOUT = 180.0


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/health"):
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def _start_health_server() -> None:
    """Render web services must bind $PORT; polling alone does not."""
    raw = (os.environ.get("PORT") or "").strip()
    if not raw:
        return
    port = int(raw)
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info("Health HTTP en 0.0.0.0:%s (/ y /health)", port)


def _api_base() -> str:
    return get_settings().api_base_url.rstrip("/")


def _wake_api() -> None:
    url = f"{_api_base()}/health"
    with httpx.Client(timeout=_WAKE_TIMEOUT) as client:
        resp = client.get(url)
        resp.raise_for_status()


def _api_chat(path: str, message: str, thread_id: str) -> str:
    _wake_api()
    url = f"{_api_base()}{path}"
    with httpx.Client(timeout=_CHAT_TIMEOUT) as client:
        resp = client.post(url, json={"message": message, "thread_id": thread_id})
        if resp.status_code >= 400:
            detail = resp.text
            try:
                detail = resp.json().get("detail", detail)
            except Exception:  # noqa: BLE001
                pass
            raise RuntimeError(str(detail))
        data = resp.json()
    return str(data.get("reply") or "No pude armar una respuesta.")


def _api_upload_pdf(filename: str, data: bytes) -> dict[str, Any]:
    _wake_api()
    url = f"{_api_base()}/api/documents/upload"
    with httpx.Client(timeout=_UPLOAD_TIMEOUT) as client:
        resp = client.post(
            url,
            files={"file": (filename, data, "application/pdf")},
        )
        if resp.status_code >= 400:
            detail = resp.text
            try:
                detail = resp.json().get("detail", detail)
            except Exception:  # noqa: BLE001
                pass
            raise RuntimeError(str(detail))
        return resp.json()


AgentMode = Literal["asistencias", "documentos"]
ChatMode = Literal["auto", "asistencias", "documentos"]

# Estado por chat (proceso del bot)
_user_mode: dict[int, ChatMode] = {}
_thread_rev: dict[tuple[int, AgentMode], int] = {}


def _is_allowed(chat_id: int) -> bool:
    allowed = get_settings().allowed_telegram_chat_ids()
    if not allowed:
        return True
    return chat_id in allowed


def _chat_mode(chat_id: int) -> ChatMode:
    return _user_mode.get(chat_id, "auto")


def _thread_id(chat_id: int, agent_mode: AgentMode) -> str:
    rev = _thread_rev.get((chat_id, agent_mode), 0)
    prefix = "att" if agent_mode == "asistencias" else "doc"
    return f"{prefix}-tg-{chat_id}-{rev}"


def _resolve_agent_mode(chat_id: int, text: str) -> AgentMode:
    mode = _chat_mode(chat_id)
    if mode == "auto":
        return classify_intent(text)
    return mode


async def _deny_if_needed(update: Update) -> bool:
    chat = update.effective_chat
    if not chat or not _is_allowed(chat.id):
        if update.effective_message:
            await update.effective_message.reply_text(
                "No tiene autorización para usar este bot."
            )
        return True
    return False


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _deny_if_needed(update):
        return
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    _user_mode[chat_id] = "auto"
    await update.effective_message.reply_text(  # type: ignore[union-attr]
        "Buenos días. Soy el asistente de la fábrica de vidrios.\n\n"
        "Puede escribir su pregunta directamente: detecto si es de "
        "asistencias o de documentos.\n\n"
        "Comandos opcionales:\n"
        "/auto — enrutado automático (recomendado)\n"
        "/asistencias — forzar solo fichadas y horas\n"
        "/documentos — forzar solo archivos\n"
        "/limpiar — reinicia la conversación del tema actual\n\n"
        "También puede enviarme un PDF cuando quiera cargarlo.\n\n"
        "Modo actual: *auto*. Escriba su pregunta cuando guste.",
        parse_mode="Markdown",
    )


async def cmd_auto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _deny_if_needed(update):
        return
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    _user_mode[chat_id] = "auto"
    await update.effective_message.reply_text(  # type: ignore[union-attr]
        "Modo *auto* activado. Escriba su pregunta y la derivo al tema correcto.",
        parse_mode="Markdown",
    )


async def cmd_asistencias(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _deny_if_needed(update):
        return
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    _user_mode[chat_id] = "asistencias"
    await update.effective_message.reply_text(  # type: ignore[union-attr]
        "Modo *asistencias* fijo. Todas las preguntas irán a fichadas y horas "
        "hasta que use /auto o /documentos.",
        parse_mode="Markdown",
    )


async def cmd_documentos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _deny_if_needed(update):
        return
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    _user_mode[chat_id] = "documentos"
    await update.effective_message.reply_text(  # type: ignore[union-attr]
        "Modo *documentos* fijo. Todas las preguntas irán a archivos "
        "hasta que use /auto o /asistencias.",
        parse_mode="Markdown",
    )


async def cmd_limpiar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _deny_if_needed(update):
        return
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    for agent_mode in ("asistencias", "documentos"):
        key = (chat_id, agent_mode)  # type: ignore[assignment]
        _thread_rev[key] = _thread_rev.get(key, 0) + 1  # type: ignore[arg-type]
    await update.effective_message.reply_text(  # type: ignore[union-attr]
        "Conversaciones reiniciadas. Puede continuar con una nueva pregunta.",
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _deny_if_needed(update):
        return
    message = update.effective_message
    if not message or not message.text:
        return
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    text = message.text.strip()
    if not text:
        return

    await message.chat.send_action("typing")
    try:
        agent_mode = await asyncio.to_thread(_resolve_agent_mode, chat_id, text)
        thread_id = _thread_id(chat_id, agent_mode)
        logger.info(
            "chat=%s mode=%s agent=%s api=%s",
            chat_id,
            _chat_mode(chat_id),
            agent_mode,
            _api_base(),
        )
        path = (
            "/api/documents/chat"
            if agent_mode == "documentos"
            else "/api/attendance/chat"
        )
        reply = await asyncio.to_thread(_api_chat, path, text, thread_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error en chat Telegram")
        reply = f"Ocurrió un problema al procesar su consulta: {exc}"

    if len(reply) > 4000:
        reply = reply[:3990] + "…"
    await message.reply_text(reply)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _deny_if_needed(update):
        return
    message = update.effective_message
    if not message or not message.document:
        return

    doc = message.document
    filename = doc.file_name or "documento.pdf"
    if not filename.lower().endswith(".pdf"):
        await message.reply_text("Por ahora solo acepto archivos PDF.")
        return

    await message.chat.send_action("typing")
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        data = bytes(await tg_file.download_as_bytearray())
        result = await asyncio.to_thread(_api_upload_pdf, filename, data)
        await message.reply_text(
            result.get("message")
            or f"Archivo cargado: {result.get('title', filename)}. Ya puede preguntarme sobre él."
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error al ingerir PDF desde Telegram")
        await message.reply_text(f"No pude cargar el archivo: {exc}")


def main() -> None:
    settings = get_settings()
    token = (settings.telegram_bot_token or "").strip()
    if not token:
        raise SystemExit(
            "Falta TELEGRAM_BOT_TOKEN en el archivo .env. "
            "Créelo con @BotFather y péguelo ahí."
        )

    logger.info("API_BASE_URL=%s", settings.api_base_url)
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("auto", cmd_auto))
    application.add_handler(CommandHandler("asistencias", cmd_asistencias))
    application.add_handler(CommandHandler("documentos", cmd_documentos))
    application.add_handler(CommandHandler("limpiar", cmd_limpiar))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    _start_health_server()
    logger.info("Bot de Telegram iniciado (polling, modo auto, vía API).")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
