"""Interfaz Streamlit — Asistencias + Documentos (memoria por thread_id)."""

from __future__ import annotations

import os
import uuid

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8001").rstrip("/")

DROPZONE_CSS = """
<style>
div[data-testid="stFileUploaderDropzone"] {
    background: #dfe6ec !important;
    border: 2px dashed #8b9aab !important;
    border-radius: 14px !important;
    min-height: 220px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 2rem 1.5rem !important;
}
div[data-testid="stFileUploaderDropzone"]:hover {
    background: #d4dde6 !important;
    border-color: #6f8296 !important;
}
div[data-testid="stFileUploaderDropzone"] section {
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 0.5rem !important;
}
div[data-testid="stFileUploaderDropzone"] button {
    display: none !important;
}
div[data-testid="stFileUploaderDropzone"] svg {
    width: 52px !important;
    height: 52px !important;
    color: #4a5563 !important;
}
div[data-testid="stFileUploaderDropzoneInstructions"] > div {
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
}
div[data-testid="stFileUploaderDropzoneInstructions"] span {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    color: #1f2a37 !important;
}
div[data-testid="stFileUploaderDropzoneInstructions"] small {
    display: none !important;
}
</style>
"""

DROPZONE_ES_JS = """
<script>
(function () {
  const root = window.parent.document;
  function localize() {
    root.querySelectorAll('[data-testid="stFileUploaderDropzoneInstructions"] span').forEach((el) => {
      const t = (el.textContent || "").trim().toLowerCase();
      if (t.includes("drag") || t.includes("browse") || t.includes("choose") || t.includes("drop")) {
        el.textContent = "Elegí un archivo o arrastralo acá";
      }
    });
    root.querySelectorAll('[data-testid="stFileUploaderDropzone"] button').forEach((btn) => {
      btn.style.display = "none";
    });
  }
  localize();
  const obs = new MutationObserver(localize);
  obs.observe(root.body, { childList: true, subtree: true });
  setTimeout(() => obs.disconnect(), 8000);
})();
</script>
"""


def api_post(path: str, json: dict | None = None, files=None, timeout: float = 120.0) -> dict:
    url = f"{API_BASE}{path}"
    with httpx.Client(timeout=timeout) as client:
        if files is not None:
            resp = client.post(url, files=files)
        else:
            resp = client.post(url, json=json or {})
        if resp.status_code >= 400:
            detail = resp.text
            try:
                detail = resp.json().get("detail", detail)
            except Exception:  # noqa: BLE001
                pass
            raise RuntimeError(str(detail))
        return resp.json()


def api_get(path: str, timeout: float = 30.0) -> dict | list:
    url = f"{API_BASE}{path}"
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(url)
        if resp.status_code >= 400:
            raise RuntimeError(resp.text)
        return resp.json()


def api_delete(path: str, timeout: float = 30.0) -> dict:
    url = f"{API_BASE}{path}"
    with httpx.Client(timeout=timeout) as client:
        resp = client.delete(url)
        if resp.status_code >= 400:
            detail = resp.text
            try:
                detail = resp.json().get("detail", detail)
            except Exception:  # noqa: BLE001
                pass
            raise RuntimeError(str(detail))
        return resp.json()


def ensure_thread(prefix: str, key: str) -> str:
    if key not in st.session_state:
        st.session_state[key] = f"{prefix}-{uuid.uuid4()}"
    return st.session_state[key]


def new_thread(prefix: str, key: str, history_key: str) -> str:
    st.session_state[key] = f"{prefix}-{uuid.uuid4()}"
    st.session_state[history_key] = []
    return st.session_state[key]


def hydrate_history(thread_id: str, history_key: str) -> list[dict[str, str]]:
    if history_key not in st.session_state:
        try:
            data = api_get(f"/api/chat/{thread_id}")
            st.session_state[history_key] = data.get("messages") or []
        except Exception:  # noqa: BLE001
            st.session_state[history_key] = []
    return st.session_state[history_key]


def render_chat(messages: list[dict[str, str]]) -> None:
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


st.set_page_config(page_title="Fábrica de Vidrios", page_icon="🪟", layout="wide")
st.markdown(DROPZONE_CSS, unsafe_allow_html=True)


@st.dialog("Subir PDF", width="large")
def upload_pdf_modal() -> None:
    st.components.v1.html(DROPZONE_ES_JS, height=0)
    if "modal_uploader_nonce" not in st.session_state:
        st.session_state["modal_uploader_nonce"] = 0

    uploaded = st.file_uploader(
        "Zona para subir PDF",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key=f"modal_pdf_uploader_{st.session_state['modal_uploader_nonce']}",
    )
    if not uploaded:
        st.caption("Solo archivos PDF.")
        return

    ok_msgs: list[str] = []
    errors: list[str] = []
    for file in uploaded:
        try:
            files = {"file": (file.name, file.getvalue(), "application/pdf")}
            with st.spinner(f"Procesando {file.name}…"):
                result = api_post("/api/documents/upload", files=files, timeout=180.0)
            ok_msgs.append(result.get("message") or f"Cargado: {result.get('title')}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{file.name}: {exc}")

    if errors:
        for err in errors:
            st.error(f"No pude cargar {err}")
        if ok_msgs:
            st.session_state["upload_flash"] = " · ".join(ok_msgs)
        return

    st.session_state["modal_uploader_nonce"] += 1
    st.session_state["upload_flash"] = " · ".join(ok_msgs) if ok_msgs else "PDF cargado."
    st.rerun()


st.title("Fábrica de Vidrios")
st.caption("Asistencias y documentos")

try:
    health = api_get("/health")
    if health.get("status") != "ok":
        st.warning("El backend respondió raro. Revisá que esté levantado.")
except Exception:
    st.error(
        f"No puedo conectar con el backend en `{API_BASE}`. "
        "Levantalo con: `uvicorn app.main:app --reload --port 8001`"
    )
    st.stop()

att_thread = ensure_thread("att", "att_thread_id")
doc_thread = ensure_thread("doc", "doc_thread_id")

mode = st.radio("Sección", ["Asistencias", "Documentos"], horizontal=True)

if mode == "Asistencias":
    st.subheader("Consultas de asistencia")
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Actualizar planilla", use_container_width=True):
            try:
                result = api_post("/api/attendance/refresh")
                st.success(
                    f"Listo. Período {result.get('period')} — "
                    f"{result.get('employee_count')} personas."
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"No pude actualizar la planilla: {exc}")
    with c2:
        if st.button("Limpiar conversación", use_container_width=True, key="clear_att"):
            old = att_thread
            att_thread = new_thread("att", "att_thread_id", "att_history")
            try:
                api_post("/api/chat/clear", json={"thread_id": old})
            except Exception:  # noqa: BLE001
                pass
            st.rerun()

    st.markdown(
        "**Ejemplos:** ¿Cuántas horas hizo Damian en septiembre? · "
        "Resumen de Producción · ¿Quién llegó tarde en Ventas?"
    )

    att_history = hydrate_history(att_thread, "att_history")
    render_chat(att_history)

    if prompt := st.chat_input("Preguntá sobre fichadas y horas…"):
        att_history.append({"role": "user", "content": prompt})
        st.session_state["att_history"] = att_history
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Revisando la planilla…"):
                try:
                    data = api_post(
                        "/api/attendance/chat",
                        json={"message": prompt, "thread_id": att_thread},
                    )
                    reply = data.get("reply") or "No pude armar una respuesta."
                except Exception as exc:  # noqa: BLE001
                    reply = f"Uy, falló la consulta: {exc}"
                st.markdown(reply)
        att_history.append({"role": "assistant", "content": reply})
        st.session_state["att_history"] = att_history

else:
    st.subheader("Documentos de clientes, ventas, etc.")
    if flash := st.session_state.pop("upload_flash", None):
        st.success(flash)
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Subir", type="primary", use_container_width=True, key="open_upload"):
            upload_pdf_modal()
    with c2:
        if st.button("Limpiar conversación", use_container_width=True, key="clear_doc"):
            old = doc_thread
            doc_thread = new_thread("doc", "doc_thread_id", "doc_history")
            try:
                api_post("/api/chat/clear", json={"thread_id": old})
            except Exception:  # noqa: BLE001
                pass
            st.rerun()

    try:
        docs = api_get("/api/documents")
        if docs:
            st.markdown("**Documentos cargados:**")
            for doc in docs:
                doc_id = str(doc.get("id") or "")
                tags = ", ".join(doc.get("tags") or []) or "—"
                col_info, col_del = st.columns([5, 1])
                with col_info:
                    st.markdown(f"**{doc.get('title')}** (`{doc_id}`) — {tags}")
                with col_del:
                    if st.button(
                        "Eliminar",
                        key=f"del_doc_{doc_id}",
                        use_container_width=True,
                    ):
                        try:
                            result = api_delete(f"/api/documents/{doc_id}")
                            st.session_state["upload_flash"] = result.get(
                                "message"
                            ) or f"Eliminé '{doc.get('title')}'."
                            st.rerun()
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"No pude eliminar: {exc}")
        else:
            st.info("Todavía no hay documentos. Tocá **Subir** para arrastrar un PDF.")
    except Exception as exc:  # noqa: BLE001
        st.warning(f"No pude listar documentos: {exc}")

    st.markdown(
        "**Ejemplos:** ¿Qué productos de laminado hay? · "
        "¿Qué condiciones de pago tiene el cliente X?"
    )

    doc_history = hydrate_history(doc_thread, "doc_history")
    render_chat(doc_history)

    if prompt := st.chat_input("Preguntá sobre los documentos…"):
        doc_history.append({"role": "user", "content": prompt})
        st.session_state["doc_history"] = doc_history
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Revisando los documentos…"):
                try:
                    data = api_post(
                        "/api/documents/chat",
                        json={"message": prompt, "thread_id": doc_thread},
                    )
                    reply = data.get("reply") or "No pude armar una respuesta."
                except Exception as exc:  # noqa: BLE001
                    reply = f"Uy, falló la consulta: {exc}"
                st.markdown(reply)
        doc_history.append({"role": "assistant", "content": reply})
        st.session_state["doc_history"] = doc_history
