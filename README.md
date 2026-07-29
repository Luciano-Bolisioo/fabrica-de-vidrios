# Fábrica de Vidrios — asistencias + documentos

App local con **FastAPI** + **Streamlit** + bot de **Telegram** y dos agentes (DeepSeek):

1. **Asistencias** — lee la planilla de Google Sheets y calcula horas por sector.
2. **Documentos** — subís PDFs; se convierten y el agente responde preguntas sobre ellos.

## Requisitos

- Python 3.11+
- API key de [DeepSeek](https://platform.deepseek.com/)
- Planilla compartida como mínimo con “Cualquiera con el enlace” (ver)
- (Opcional) token de bot de Telegram vía [@BotFather](https://t.me/BotFather)

## Setup

```bash
cd "c:\Users\lucia\Desktop\fabrica de vidirios"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Editá `.env` y pegá tu `DEEPSEEK_API_KEY`.  
Para Telegram, agregá también `TELEGRAM_BOT_TOKEN` (y opcionalmente `TELEGRAM_ALLOWED_CHAT_IDS` con tu chat id).

## Levantar

Terminal 1 — API:

```bash
.venv\Scripts\activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

Terminal 2 — UI:

```bash
.venv\Scripts\activate
streamlit run ui/streamlit_app.py
```

Abrí http://localhost:8501

Terminal 3 — Bot de Telegram (opcional):

```bash
.venv\Scripts\activate
python -m app.telegram_bot
```

Comandos del bot: `/start`, `/asistencias`, `/documentos`, `/limpiar`.  
En modo documentos también acepta PDF.

> Nota: en esta máquina el puerto 8000 puede estar bloqueado; usamos **8001**.

## Horarios por sector

| Sector | Jornada |
|---|---|
| Administración | 8–16 (8 h) |
| Ventas | 8–14 (6 h) |
| Producción | 8–17 (9 h) |
| Maestranza | sin horario fijo (solo horas reales) |

## Planilla

ID por defecto: `1KW8Q1YUzijV9uFmQj-x5ZMwxkCMC1rBZzt2HiVCOlYE`

Si al arrancar falla la lectura, en Google Sheets: **Compartir → Cualquiera con el enlace → Lector**.

## Deploy en Render

Repo: https://github.com/Luciano-Bolisioo/fabrica-de-vidrios

| Servicio | URL | Start |
|---|---|---|
| API | https://fabrica-vidrios-api.onrender.com | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| UI | https://fabrica-vidrios-ui.onrender.com | `streamlit run ui/streamlit_app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true` |

Build (ambos): `pip install -r requirements.txt`

Env API: `DEEPSEEK_API_KEY`, `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL`, `GOOGLE_SHEET_ID`.  
Env UI: `API_BASE_URL=https://fabrica-vidrios-api.onrender.com`

Health: `GET /health` en la API.  
Nota: free duerme tras inactividad; el disco es efímero (PDFs se pierden al redeploy).

## Notas

- Los agentes responden de forma amable y respetuosa, y **no nombran tecnologías**.
- Los PDFs quedan en `data/uploads/` y el conocimiento procesado en `data/okf/`.
- La memoria del chat de Telegram usa `InMemorySaver` (se pierde al reiniciar el proceso del bot).
