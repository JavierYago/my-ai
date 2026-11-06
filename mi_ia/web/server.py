"""Servidor web de Mi IA. Solo escucha en tu PC (127.0.0.1)."""
import json
import queue
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..agent import Agent
from ..chats import ChatStore
from ..config import get_settings
from ..llm import ChatLLM, LLMError
from ..memory import Memory
from ..tools import build_tools

STATIC = Path(__file__).parent / "static"
CONFIRM_TIMEOUT = 180  # segundos para aceptar o rechazar la ejecución de código

settings = get_settings()
llm = ChatLLM(settings.llm_base_url, settings.llm_api_key, settings.llm_model,
              settings.llm_temperature, settings.llm_timeout)
memory = Memory(settings.data_dir)
store = ChatStore(settings.data_dir)
tools = build_tools(settings)

# El modelo corre en tu CPU: solo una respuesta a la vez
busy = threading.Lock()
pending_confirms: dict[str, dict] = {}

app = FastAPI(title=settings.ai_name, docs_url=None, redoc_url=None, openapi_url=None)
ALLOWED_HOSTS = {f"127.0.0.1:{settings.web_port}", f"localhost:{settings.web_port}"}


@app.middleware("http")
async def only_local(request: Request, call_next):
    """Bloquea peticiones que no vengan de esta misma web (DNS rebinding y CSRF)."""
    if request.headers.get("host") not in ALLOWED_HOSTS:
        return JSONResponse({"detail": "Host no permitido"}, status_code=403)
    origin = request.headers.get("origin")
    if request.method != "GET" and origin and origin.split("://", 1)[-1] not in ALLOWED_HOSTS:
        return JSONResponse({"detail": "Origen no permitido"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; "
        "script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    )
    return response


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)


class ConfirmIn(BaseModel):
    allow: bool


class FeedbackIn(BaseModel):
    turn_id: str = Field(pattern=r"^[a-f0-9]{12}$")
    rating: str = Field(pattern=r"^(good|bad|corrected)$")
    correction: str | None = Field(default=None, max_length=20_000)


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)


def _chat_or_404(chat_id: str) -> dict:
    try:
        return store.get(chat_id)
    except KeyError:
        raise HTTPException(404, "Conversación no encontrada") from None


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/info")
def info():
    return {"name": settings.ai_name, "model": settings.llm_model}


@app.get("/api/chats")
def list_chats():
    return store.all()


@app.post("/api/chats")
def create_chat():
    return store.create()


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str):
    return _chat_or_404(chat_id)


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str):
    _chat_or_404(chat_id)
    store.delete(chat_id)
    return {"ok": True}


@app.post("/api/chats/{chat_id}/messages")
def send_message(chat_id: str, body: MessageIn):
    chat = _chat_or_404(chat_id)
    if not busy.acquire(blocking=False):
        raise HTTPException(409, "Ya estoy respondiendo otra pregunta. Espera a que termine.")

    events: queue.Queue = queue.Queue()

    def emit(event: dict) -> None:
        events.put(json.dumps(event, ensure_ascii=False) + "\n")

    def on_event(tool: str, args: dict) -> None:
        if tool == "_discard":
            emit({"type": "discard"})
        else:
            detail = args.get("query") or args.get("url") or args.get("path") or ""
            emit({"type": "tool", "name": tool, "detail": detail})

    def confirm(tool: str, args: dict) -> bool:
        confirm_id = uuid.uuid4().hex
        waiter = {"event": threading.Event(), "allow": False}
        pending_confirms[confirm_id] = waiter
        emit({"type": "confirm", "id": confirm_id, "tool": tool, "code": args.get("code", "")})
        waiter["event"].wait(CONFIRM_TIMEOUT)
        pending_confirms.pop(confirm_id, None)
        return waiter["allow"]

    def worker() -> None:
        try:
            agent = Agent(llm, tools, memory, name=settings.ai_name,
                          max_steps=settings.max_tool_steps, confirm=confirm, on_event=on_event)
            agent.history = [{"role": m["role"], "content": m["content"]}
                             for m in chat["messages"]][-12:]
            answer = agent.ask(body.text, on_token=lambda t: emit({"type": "token", "text": t}))
            turn_id = memory.log_turn(chat_id, body.text, answer, agent.last_tools)
            store.add_turn(chat, body.text, answer, turn_id, agent.last_tools)
            emit({"type": "done", "answer": answer, "turn_id": turn_id, "title": chat["title"]})
        except LLMError as exc:
            emit({"type": "error", "message": str(exc)})
        except Exception as exc:
            emit({"type": "error", "message": f"Error inesperado: {type(exc).__name__}"})
        finally:
            busy.release()
            events.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while (item := events.get()) is not None:
            yield item

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.post("/api/confirm/{confirm_id}")
def answer_confirm(confirm_id: str, body: ConfirmIn):
    waiter = pending_confirms.get(confirm_id)
    if waiter is None:
        raise HTTPException(404, "Esta petición ya no está pendiente")
    waiter["allow"] = body.allow
    waiter["event"].set()
    return {"ok": True}


@app.post("/api/feedback")
def feedback(body: FeedbackIn):
    if body.rating == "corrected" and not body.correction:
        raise HTTPException(400, "Falta la corrección")
    memory.rate(body.turn_id, body.rating, body.correction)
    return {"ok": True}


@app.get("/api/notes")
def get_notes():
    return memory.notes()


@app.post("/api/notes")
def add_note(body: NoteIn):
    memory.add_note(body.text)
    return memory.notes()


app.mount("/static", StaticFiles(directory=STATIC), name="static")
