"""Cliente para cualquier modelo con API compatible con OpenAI (Ollama, LM Studio, Groq...)."""
import json
from typing import Callable

import httpx

from .security import redact


class LLMError(Exception):
    pass


def _merge_tool_call(calls: list[dict], tc: dict) -> None:
    """Las llamadas a herramientas llegan en trozos durante el streaming; aquí se juntan."""
    index = tc.get("index", len(calls))
    fn = tc.get("function") or {}
    new_id = tc.get("id")
    if index >= len(calls) or (new_id and calls[index]["id"] and calls[index]["id"] != new_id):
        calls.append({"id": new_id or f"call_{len(calls)}", "type": "function",
                      "function": {"name": "", "arguments": ""}})
        index = len(calls) - 1
    entry = calls[index]
    entry["function"]["name"] += fn.get("name") or ""
    args = fn.get("arguments")
    if args:
        entry["function"]["arguments"] += args if isinstance(args, str) else json.dumps(args)


class ChatLLM:
    def __init__(self, base_url: str, api_key: str, model: str,
                 temperature: float = 0.3, timeout: float = 300):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        # La clave solo viaja en la cabecera; nunca se imprime ni se guarda
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = httpx.Client(headers=headers, timeout=timeout)

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Envía la conversación y devuelve el mensaje del asistente (formato OpenAI)."""
        body = {"model": self.model, "messages": messages, "temperature": self.temperature}
        if tools:
            body["tools"] = tools
        data = self._post("/chat/completions", body)
        try:
            return data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"Respuesta inesperada del modelo: {str(data)[:300]}") from exc

    def chat_stream(self, messages: list[dict], tools: list[dict] | None = None,
                    on_token: Callable[[str], None] | None = None) -> dict:
        """Como chat(), pero va entregando el texto trozo a trozo mientras se genera."""
        body = {"model": self.model, "messages": messages,
                "temperature": self.temperature, "stream": True}
        if tools:
            body["tools"] = tools
        content = ""
        calls: list[dict] = []
        try:
            with self._client.stream("POST", f"{self.base_url}/chat/completions", json=body) as r:
                if r.status_code >= 400:
                    r.read()
                    r.raise_for_status()
                for line in r.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    choices = json.loads(data).get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    if delta.get("content"):
                        content += delta["content"]
                        if on_token:
                            on_token(delta["content"])
                    for tc in delta.get("tool_calls") or []:
                        _merge_tool_call(calls, tc)
        except httpx.HTTPError as exc:
            raise LLMError(self._explain(exc)) from exc
        return {"role": "assistant", "content": content, "tool_calls": calls or None}

    def list_models(self) -> list[str]:
        try:
            r = self._client.get(f"{self.base_url}/models")
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(self._explain(exc)) from exc
        return [m.get("id", "?") for m in r.json().get("data", [])]

    def _post(self, path: str, body: dict) -> dict:
        try:
            r = self._client.post(f"{self.base_url}{path}", json=body)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as exc:
            raise LLMError(self._explain(exc)) from exc

    def _explain(self, exc: httpx.HTTPError) -> str:
        if isinstance(exc, httpx.ConnectError):
            return (f"No puedo conectar con el modelo en {self.base_url}. "
                    "¿Está Ollama abierto? Prueba: ollama serve")
        if isinstance(exc, httpx.TimeoutException):
            return "El modelo tardó demasiado. Sube LLM_TIMEOUT en .env o usa un modelo más pequeño."
        if isinstance(exc, httpx.HTTPStatusError):
            detail = redact(exc.response.text[:300])
            if "out-of-memory" in detail or "unable to allocate" in detail:
                return (f"El modelo '{self.model}' no cabe en la RAM libre. Cierra programas que "
                        "gasten mucha memoria (navegador, Discord...) o usa un modelo más pequeño "
                        "en .env, por ejemplo LLM_MODEL=qwen2.5-coder:1.5b")
            if exc.response.status_code == 404:
                return (f"Modelo '{self.model}' no encontrado. "
                        f"Descárgalo con: ollama pull {self.model}  ({detail})")
            return f"Error {exc.response.status_code} del modelo: {detail}"
        return f"Error de red: {type(exc).__name__}"
