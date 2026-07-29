from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.agents.attendance_agent import get_attendance_history, run_attendance_chat
from app.agents.documents_agent import get_documents_history, run_documents_chat
from app.config import get_settings
from app.models.schemas import (
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    ClearChatRequest,
    DocumentInfo,
    UploadResponse,
)
from app.services import okf_ingest, okf_store, sheets

app = FastAPI(title="Fábrica de Vidrios — Agentes", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    get_settings()
    okf_store.rebuild_index()
    try:
        sheets.refresh_sheet()
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] No se pudo cargar la planilla: {exc}")


def _history_for_thread(thread_id: str) -> list[dict[str, str]]:
    if thread_id.startswith("doc-"):
        return get_documents_history(thread_id)
    return get_attendance_history(thread_id)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/attendance/chat", response_model=ChatResponse)
def attendance_chat(payload: ChatRequest) -> ChatResponse:
    try:
        reply = run_attendance_chat(payload.message, payload.thread_id)
        return ChatResponse(reply=reply, thread_id=payload.thread_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/attendance/refresh")
def attendance_refresh() -> dict:
    try:
        return sheets.refresh_sheet()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/documents/upload", response_model=UploadResponse)
async def documents_upload(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Falta el nombre del archivo.")
    lower = file.filename.lower()
    if not lower.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Por ahora solo acepto PDF.")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    try:
        result = okf_ingest.ingest_pdf(data, file.filename)
        return UploadResponse(
            id=result["id"],
            title=result["title"],
            message=result["message"],
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/documents", response_model=list[DocumentInfo])
def documents_list() -> list[DocumentInfo]:
    docs = okf_store.list_documents()
    return [DocumentInfo(**d) for d in docs]


@app.post("/api/documents/chat", response_model=ChatResponse)
def documents_chat(payload: ChatRequest) -> ChatResponse:
    try:
        reply = run_documents_chat(payload.message, payload.thread_id)
        return ChatResponse(reply=reply, thread_id=payload.thread_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/chat/{thread_id}", response_model=ChatHistoryResponse)
def chat_history(thread_id: str) -> ChatHistoryResponse:
    try:
        messages = _history_for_thread(thread_id)
        return ChatHistoryResponse(thread_id=thread_id, messages=messages)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/chat/clear")
def chat_clear(payload: ClearChatRequest) -> dict:
    # InMemorySaver no borra fácil: el client genera un thread_id nuevo.
    # Este endpoint confirma el clear del lado UI.
    return {"ok": True, "cleared": payload.thread_id}
