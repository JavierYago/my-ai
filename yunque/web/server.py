"""Servidor web de Yunque. Solo escucha en tu PC (127.0.0.1)."""
import base64
import json
import queue
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..agent import Agent
from ..chats import ChatStore
from ..config import get_settings
from ..connectors import ConnectorManager
from ..llm import ChatLLM, LLMError
from ..memory import Memory
from ..security import safe_path
from ..skills import SkillLibrary
from ..tools import build_tools
from ..tools.media import GENERATED
from ..voice import SentenceSplitter, Voice

STATIC = Path(__file__).parent / "static"
CONFIRM_TIMEOUT = 180  # segundos para aceptar o rechazar una herramienta
MAX_AUDIO = 10_000_000  # 10 MB por mensaje de voz

settings = get_settings()
llm = ChatLLM(settings.llm_base_url, settings.llm_api_key, settings.llm_model,
              settings.llm_temperature, settings.llm_timeout)
memory = Memory(settings.data_dir)
store = ChatStore(settings.data_dir)
skills = SkillLibrary(settings.skills_dir)
voice = Voice(settings.models_dir, settings.voice_name, settings.whisper_model,
              settings.voice_language)
base_tools = build_tools(settings, voice=voice, skills=skills)
connectors = ConnectorManager(settings.connectors_file, settings.data_dir / "connectors.log")

# El modelo corre en tu CPU: solo una respuesta a la vez
busy = threading.Lock()
pending_confirms: dict[str, dict] = {}


def all_tools() -> dict:
    return {**base_tools, **connectors.tools()}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Los conectores se conectan en segundo plano para que la web abra al instante
    threading.Thread(target=connectors.start, daemon=True).start()
    yield
    connectors.stop()


app = FastAPI(title=settings.ai_name, docs_url=None, redoc_url=None, openapi_url=None,
              lifespan=lifespan)
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
        "default-src 'self'; img-src 'self' data: https:; media-src 'self' blob: data:; "
        "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    response.headers["Permissions-Policy"] = "microphone=(self), camera=()"
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


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=5_000)


class ToggleIn(BaseModel):
    enabled: bool


def _chat_or_404(chat_id: str) -> dict:
    try:
        return store.get(chat_id)
    except KeyError:
        raise HTTPException(404, "Conversación no encontrada") from None


def _media_urls(media: list[dict]) -> list[dict]:
    return [{**m, "url": f"/files/{m['path']}"} for m in media]


# ---------- Páginas y datos básicos ----------

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/info")
def info():
    return {"name": settings.ai_name, "model": settings.llm_model,
            "images": bool(settings.pollinations_api_key)}


@app.get("/files/{path:path}")
def get_file(path: str):
    """Sirve las imágenes y audios generados (solo de workspace/generated)."""
    try:
        target = safe_path(settings.workspace_dir / GENERATED, path.removeprefix(f"{GENERATED}/"))
    except PermissionError:
        raise HTTPException(404) from None
    if not target.is_file():
        raise HTTPException(404)
    return FileResponse(target)


# ---------- Conversaciones ----------

@app.get("/api/chats")
def list_chats():
    return store.all()


@app.post("/api/chats")
def create_chat():
    return store.create()


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str):
    chat = _chat_or_404(chat_id)
    for m in chat["messages"]:
        m["media"] = _media_urls(m.get("media", []))
    return chat


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str):
    _chat_or_404(chat_id)
    store.delete(chat_id)
    return {"ok": True}


def _run_turn(chat: dict, text: str, emit, voice_mode: bool = False) -> None:
    """Ejecuta una pregunta del agente y emite eventos (texto, herramientas, imágenes...)."""

    def on_event(tool: str, args: dict) -> None:
        if tool == "_discard":
            emit({"type": "discard"})
        elif tool == "_media":
            emit({"type": "media", **_media_urls([args])[0]})
        else:
            detail = args.get("query") or args.get("url") or args.get("path") or \
                args.get("prompt") or args.get("name") or ""
            emit({"type": "tool", "name": tool, "detail": str(detail)[:200]})

    def confirm(tool: str, args: dict) -> bool:
        confirm_id = uuid.uuid4().hex
        waiter = {"event": threading.Event(), "allow": False}
        pending_confirms[confirm_id] = waiter
        emit({"type": "confirm", "id": confirm_id, "tool": tool,
              "code": args.get("code") or json.dumps(args, ensure_ascii=False, indent=2)})
        waiter["event"].wait(CONFIRM_TIMEOUT)
        pending_confirms.pop(confirm_id, None)
        return waiter["allow"]

    agent = Agent(llm, all_tools(), memory, name=settings.ai_name,
                  max_steps=settings.max_tool_steps, confirm=confirm, on_event=on_event,
                  skills=skills)
    agent.history = [{"role": m["role"], "content": m["content"]}
                     for m in chat["messages"]][-12:]
    splitter = SentenceSplitter() if voice_mode else None

    def on_token(token: str) -> None:
        emit({"type": "token", "text": token})
        if splitter:
            for sentence in splitter.feed(token):
                emit({"type": "audio", "data": base64.b64encode(voice.synthesize(sentence)).decode()})

    answer = agent.ask(text, on_token=on_token, voice=voice_mode)
    if splitter:
        for sentence in splitter.flush():
            emit({"type": "audio", "data": base64.b64encode(voice.synthesize(sentence)).decode()})
    turn_id = memory.log_turn(chat["id"], text, answer, agent.last_tools)
    store.add_turn(chat, text, answer, turn_id, agent.last_tools, agent.last_media)
    emit({"type": "done", "answer": answer, "turn_id": turn_id, "title": chat["title"]})


def _stream(work) -> StreamingResponse:
    """Ejecuta `work(emit)` en otro hilo y envía sus eventos al navegador según llegan."""
    if not busy.acquire(blocking=False):
        raise HTTPException(409, "Ya estoy respondiendo otra pregunta. Espera a que termine.")
    events: queue.Queue = queue.Queue()

    def emit(event: dict) -> None:
        events.put(json.dumps(event, ensure_ascii=False) + "\n")

    def worker() -> None:
        try:
            work(emit)
        except LLMError as exc:
            emit({"type": "error", "message": str(exc)})
        except Exception as exc:
            emit({"type": "error", "message": f"Error inesperado: {type(exc).__name__}: {exc}"[:300]})
        finally:
            busy.release()
            events.put(None)

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while (item := events.get()) is not None:
            yield item

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.post("/api/chats/{chat_id}/messages")
def send_message(chat_id: str, body: MessageIn):
    chat = _chat_or_404(chat_id)
    return _stream(lambda emit: _run_turn(chat, body.text, emit))


@app.post("/api/chats/{chat_id}/voice")
async def voice_turn(chat_id: str, audio: UploadFile):
    """Llamada de voz: recibe tu audio, lo transcribe y responde hablando."""
    chat = _chat_or_404(chat_id)
    data = await audio.read(MAX_AUDIO + 1)
    if len(data) > MAX_AUDIO:
        raise HTTPException(413, "Audio demasiado largo")

    def work(emit):
        text = voice.transcribe(data)
        emit({"type": "transcript", "text": text})
        if not text:
            emit({"type": "done", "answer": "", "turn_id": None, "title": chat["title"]})
            return
        _run_turn(chat, text, emit, voice_mode=True)

    return _stream(work)


@app.post("/api/tts")
def text_to_speech(body: TextIn):
    """Lee un texto en voz alta (botón de altavoz de cada respuesta)."""
    return Response(voice.synthesize(body.text), media_type="audio/wav")


@app.post("/api/voice/warmup")
def warmup_voice():
    """Prepara la llamada: carga los modelos de voz (la primera vez se descargan) y hace que
    el modelo de lenguaje lea ya sus instrucciones, para que la primera respuesta sea rápida."""
    voice.transcribe(voice.synthesize("Hola."))
    agent = Agent(llm, all_tools(), memory, name=settings.ai_name, skills=skills)
    system, schemas = agent.prompt_and_tools(voice=True)
    try:
        llm.chat([{"role": "system", "content": system}, {"role": "user", "content": "Hola"}],
                 tools=schemas, max_tokens=1)
    except LLMError as exc:
        raise HTTPException(503, str(exc)) from None
    return {"ok": True}


@app.post("/api/confirm/{confirm_id}")
def answer_confirm(confirm_id: str, body: ConfirmIn):
    waiter = pending_confirms.get(confirm_id)
    if waiter is None:
        raise HTTPException(404, "Esta petición ya no está pendiente")
    waiter["allow"] = body.allow
    waiter["event"].set()
    return {"ok": True}


# ---------- Entrenamiento y memoria ----------

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


# ---------- Habilidades y conectores ----------

@app.get("/api/skills")
def list_skills():
    return [{"name": n, "description": d} for n, d in skills.summary()]


@app.get("/api/connectors")
def list_connectors():
    return [vars(s) for s in connectors.status.values()]


@app.post("/api/connectors/{name}")
def toggle_connector(name: str, body: ToggleIn):
    try:
        connectors.set_enabled(name, body.enabled)
    except KeyError:
        raise HTTPException(404, "Conector no encontrado") from None
    connectors.restart()
    return list_connectors()


app.mount("/static", StaticFiles(directory=STATIC), name="static")
