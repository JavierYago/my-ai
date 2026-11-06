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


class Agent:
    def __init__(self, llm: ChatLLM, tools: dict[str, Tool], memory: Memory,
                 name: str = "Mi IA", max_steps: int = 6,
                 confirm: ConfirmFn | None = None, on_event: EventFn | None = None):
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self.name = name
        self.max_steps = max_steps
        self.confirm = confirm or (lambda tool, args: False)
        self.on_event = on_event or (lambda tool, args: None)
        self.history: list[dict] = []
        self.last_tools: list[str] = []

    def reset(self) -> None:
        self.history = []

    def ask(self, question: str, on_token: Callable[[str], None] | None = None) -> str:
        """Responde a la pregunta. Si se pasa on_token, el texto llega en streaming."""
        system = build_system_prompt(self.name, self.memory.relevant_notes(question))
        messages = [{"role": "system", "content": system}, *self.history,
                    {"role": "user", "content": question}]
        schemas = [t.schema() for t in self.tools.values()]
        self.last_tools = []

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

        self.history += [{"role": "user", "content": question},
                         {"role": "assistant", "content": answer}]
        self.history = self.history[-MAX_HISTORY:]
        return answer

    def _run_tool(self, call: dict) -> str:
        name = call["function"]["name"]
        tool = self.tools.get(name)
        if tool is None:
            return f"Error: la herramienta '{name}' no existe."
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
        name = data.get("name") if isinstance(data, dict) else None
        if name not in self.tools:
            return []
        args = data.get("arguments", data.get("parameters", {}))
        return [{"id": "call_text", "type": "function",
                 "function": {"name": name, "arguments": _clean_args(args)}}]
