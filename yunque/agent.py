"""El agente: habla con el modelo y ejecuta las herramientas que pide."""
import json
import re
from typing import Callable

from .llm import ChatLLM
from .memory import Memory
from .prompts import build_system_prompt
from .security import redact
from .tools import Tool

MAX_TOOL_RESULT = 8_000
MAX_HISTORY = 12  # mensajes previos que se recuerdan dentro de una conversación
VOICE_TOOLS = {"web_search", "fetch_url"}  # herramientas disponibles durante una llamada

ConfirmFn = Callable[[str, dict], bool]
EventFn = Callable[[str, dict], None]


def _unwrap(value):
    """Los modelos pequeños a veces copian el esquema: {"type": "string", "description": "x"} -> "x"."""
    if isinstance(value, dict) and "type" in value:
        for key in ("value", "description", "content"):
            if isinstance(value.get(key), str):
                return value[key]
    return value


def _clean_args(args) -> str:
    """Devuelve los argumentos como JSON limpio y ordenado (o tal cual si no son JSON)."""
    if isinstance(args, str):
        try:
            args = json.loads(args or "{}")
        except json.JSONDecodeError:
            return args
    if isinstance(args, dict):
        args = {k: _unwrap(v) for k, v in args.items()}
    return json.dumps(args, ensure_ascii=False, sort_keys=True)


def _add_notices(answer: str, notices: list[str]) -> str:
    """Garantiza que el usuario sepa por qué falló una herramienta.

    Los modelos pequeños a veces contestan "no puedo ayudarte" en vez de explicar el error.
    Si la respuesta es corta, se sustituye por la explicación; si es larga, se añade al final.
    """
    if not notices:
        return answer
    text = "\n\n".join(f"⚠️ {n}" for n in dict.fromkeys(notices))
    if len(answer.strip()) < 160:
        return text
    if all(n[:40] in answer for n in notices):
        return answer
    return f"{answer}\n\n{text}"


class Agent:
    def __init__(self, llm: ChatLLM, tools: dict[str, Tool], memory: Memory,
                 name: str = "Yunque", max_steps: int = 6,
                 confirm: ConfirmFn | None = None, on_event: EventFn | None = None,
                 skills=None):
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self.name = name
        self.max_steps = max_steps
        self.confirm = confirm or (lambda tool, args: False)
        self.on_event = on_event or (lambda tool, args: None)
        self.skills = skills
        self.history: list[dict] = []
        self.last_tools: list[str] = []
        self.last_media: list[dict] = []
        self.last_notices: list[str] = []

    def reset(self) -> None:
        self.history = []

    def prompt_and_tools(self, question: str = "", voice: bool = False) -> tuple[str, list[dict]]:
        """Instrucciones y herramientas que recibe el modelo.

        En una llamada de voz se envían menos cosas: el modelo lee menos y contesta antes.
        """
        notes = self.memory.relevant_notes(question) if question else []
        skills = self.skills.summary() if self.skills and not voice else None
        system = build_system_prompt(self.name, notes, skills, voice=voice)
        schemas = [t.schema() for name, t in self.tools.items()
                   if not voice or name in VOICE_TOOLS]
        return system, schemas

    def ask(self, question: str, on_token: Callable[[str], None] | None = None,
            voice: bool = False) -> str:
        """Responde a la pregunta.

        on_token: si se pasa, el texto llega en streaming.
        voice: modo llamada (respuestas cortas, sin herramientas que pidan confirmación).
        """
        system, schemas = self.prompt_and_tools(question, voice)
        messages = [{"role": "system", "content": system}, *self.history,
                    {"role": "user", "content": question}]
        self.last_tools = []
        self.last_media = []
        self.last_notices = []

        def call_llm(msgs: list[dict], tools: list[dict] | None) -> dict:
            if on_token:
                return self.llm.chat_stream(msgs, tools=tools, on_token=on_token)
            return self.llm.chat(msgs, tools=tools)

        answer = None
        done_calls: set[str] = set()
        repeats = 0
        for _ in range(self.max_steps):
            reply = call_llm(messages, schemas)
            calls = self._tool_calls(reply)
            if not calls:
                answer = reply.get("content") or ""
                break
            if on_token and not reply.get("tool_calls"):
                # El texto emitido era una llamada a herramienta escrita como JSON: se descarta
                self.on_event("_discard", {})
            messages.append({"role": "assistant", "content": reply.get("content") or "",
                             "tool_calls": calls})
            for call in calls:
                key = call["function"]["name"] + call["function"]["arguments"]
                if key in done_calls:
                    # Los modelos pequeños a veces repiten la misma llamada en bucle
                    repeats += 1
                    result = ("Ya hiciste exactamente esta llamada y su resultado está más arriba. "
                              "No la repitas: usa esa información para responder al usuario.")
                else:
                    done_calls.add(key)
                    result = self._run_tool(call)
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
            if repeats >= 2:
                break
        if answer is None:
            if on_token:
                self.on_event("_discard", {})
            messages.append({"role": "user", "content":
                             "Ya no puedes usar más herramientas. Responde ahora a mi pregunta "
                             "con la información que has obtenido."})
            answer = call_llm(messages, None).get("content") or ""

        answer = _add_notices(answer, self.last_notices)
        self.history += [{"role": "user", "content": question},
                         {"role": "assistant", "content": answer}]
        self.history = self.history[-MAX_HISTORY:]
        return answer

    def _run_tool(self, call: dict) -> str:
        name = call["function"]["name"]
        tool = self.tools.get(name)
        if tool is None:
            return (f"Error: la herramienta '{name}' no existe. Las herramientas disponibles son: "
                    f"{', '.join(self.tools)}. Las habilidades se cargan con use_skill.")
        try:
            args = json.loads(call["function"]["arguments"] or "{}")
        except json.JSONDecodeError:
            return "Error: argumentos JSON no válidos."
        if not isinstance(args, dict):
            return "Error: los argumentos deben ser un objeto JSON."
        self.last_tools.append(name)
        self.on_event(name, args)
        if tool.needs_confirmation and not self.confirm(name, args):
            return "El usuario no ha permitido ejecutar esta herramienta."
        try:
            result = tool.func(**args)
        except PermissionError as exc:
            result = f"Bloqueado por seguridad: {exc}"
        except TypeError as exc:
            result = f"Error: argumentos incorrectos para {name}: {exc}"
        except Exception as exc:  # una herramienta que falla no debe tumbar la IA
            result = f"Error en {name}: {type(exc).__name__}: {exc}"
        if isinstance(result, dict):  # imagen o audio generado, o un error explicado
            media = result.get("media")
            if media:
                self.last_media.append(media)
                self.on_event("_media", media)
            if result.get("notice"):
                self.last_notices.append(result["notice"])
            result = result.get("text", "")
        return redact(str(result))[:MAX_TOOL_RESULT]

    def _tool_calls(self, reply: dict) -> list[dict]:
        calls = reply.get("tool_calls") or []
        normalized = []
        for i, c in enumerate(calls):
            fn = c.get("function", {})
            normalized.append({"id": c.get("id") or f"call_{i}", "type": "function",
                               "function": {"name": fn.get("name", ""),
                                            "arguments": _clean_args(fn.get("arguments"))}})
        return normalized or self._parse_text_tool_call(reply.get("content") or "")

    def _parse_text_tool_call(self, content: str) -> list[dict]:
        """Los modelos pequeños a veces escriben la llamada como texto JSON; la recuperamos."""
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
        if not text.startswith("{"):
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, dict) or not isinstance(data.get("name"), str):
            return []
        name = data["name"]
        args = data.get("arguments", data.get("parameters", {}))
        skill_names = {n for n, _ in self.skills.summary()} if self.skills else set()
        if name not in self.tools:
            if name in skill_names and "use_skill" in self.tools:
                # El modelo ha llamado a una habilidad como si fuera una herramienta
                name, args = "use_skill", {"name": name}
            elif not set(data) <= {"name", "arguments", "parameters"} or len(data) < 2:
                return []  # es un JSON normal de la respuesta, no una llamada
            # Si la herramienta no existe, _run_tool le dirá al modelo cuáles hay
        return [{"id": "call_text", "type": "function",
                 "function": {"name": name, "arguments": _clean_args(args)}}]
