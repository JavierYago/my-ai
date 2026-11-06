"""Conectores: une la IA a servicios externos usando MCP (Model Context Protocol).

MCP es el estándar abierto que usan Claude y otras IAs para conectarse a GitHub, Notion,
bases de datos, archivos... Cada servidor MCP aporta herramientas nuevas a la IA.

La configuración está en connectors.json (copia connectors.example.json). Las claves NO se
escriben ahí: se ponen como ${NOMBRE_VARIABLE} y se leen del archivo .env.
"""
import asyncio
import json
import os
import re
import shutil
import threading
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path

from .security import redact
from .tools import Tool

_VAR = re.compile(r"\$\{([A-Za-z0-9_]+)\}")
_SAFE_NAME = re.compile(r"[^a-zA-Z0-9_-]")
CONNECT_TIMEOUT = 90  # npx puede tardar en descargar el servidor la primera vez


def expand_vars(value: str) -> str:
    """Sustituye ${VAR} por el valor de la variable de entorno (del .env)."""
    def sub(match: re.Match) -> str:
        name = match.group(1)
        if name not in os.environ:
            raise KeyError(f"Falta la variable {name} en el archivo .env")
        return os.environ[name]
    return _VAR.sub(sub, value)


def _describe(exc: BaseException) -> str:
    # anyio agrupa los errores; mostramos el primero, que es el que importa
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return redact(f"{type(exc).__name__}: {exc}")[:300]


@dataclass
class ConnectorStatus:
    name: str
    description: str = ""
    enabled: bool = False
    connected: bool = False
    error: str = ""
    tools: list[str] = field(default_factory=list)


class ConnectorManager:
    def __init__(self, config_path: Path, log_path: Path, call_timeout: float = 120):
        self.config_path = config_path
        self.log_path = log_path
        self.call_timeout = call_timeout
        self.status: dict[str, ConnectorStatus] = {}
        self._tools: dict[str, Tool] = {}
        self._sessions: dict = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None
        self._lock = threading.Lock()

    # ---------- Configuración ----------

    def read_config(self) -> dict:
        if not self.config_path.exists():
            return {"servers": {}}
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def set_enabled(self, name: str, enabled: bool) -> None:
        config = self.read_config()
        if name not in config.get("servers", {}):
            raise KeyError(name)
        config["servers"][name]["enabled"] = enabled
        self.config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                                    encoding="utf-8")

    # ---------- Arranque y parada ----------

    def start(self) -> None:
        """Conecta todos los servidores activados (bloquea hasta que conectan o fallan)."""
        with self._lock:
            servers = self.read_config().get("servers", {})
            self.status = {
                name: ConnectorStatus(name, cfg.get("description", ""), cfg.get("enabled", False))
                for name, cfg in servers.items()
            }
            active = {n: c for n, c in servers.items() if c.get("enabled", False)}
            if not active:
                return
            self._loop = asyncio.new_event_loop()
            threading.Thread(target=self._loop.run_forever, daemon=True).start()
            self._stop = asyncio.Event()
            waiters = []
            for name, cfg in active.items():
                ready = threading.Event()
                asyncio.run_coroutine_threadsafe(self._run_server(name, cfg, ready), self._loop)
                waiters.append(ready)
            for ready in waiters:
                ready.wait(CONNECT_TIMEOUT)

    def stop(self) -> None:
        with self._lock:
            if self._loop and self._stop:
                self._loop.call_soon_threadsafe(self._stop.set)
                self._loop.call_soon_threadsafe(self._loop.stop)
            self._loop = None
            self._sessions.clear()
            self._tools.clear()

    def restart(self) -> None:
        self.stop()
        self.start()

    def tools(self) -> dict[str, Tool]:
        return dict(self._tools)

    # ---------- Conexión con cada servidor ----------

    async def _open_transport(self, stack: AsyncExitStack, cfg: dict):
        from mcp import StdioServerParameters
        from mcp.client.stdio import get_default_environment, stdio_client
        from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

        if "url" in cfg:
            headers = {k: expand_vars(v) for k, v in cfg.get("headers", {}).items()}
            client = await stack.enter_async_context(create_mcp_http_client(headers=headers))
            streams = await stack.enter_async_context(
                streamable_http_client(expand_vars(cfg["url"]), http_client=client))
        else:
            # El servidor solo recibe las variables básicas del sistema + las que declares
            env = get_default_environment()
            env.update({k: expand_vars(v) for k, v in cfg.get("env", {}).items()})
            params = StdioServerParameters(
                command=shutil.which(cfg["command"]) or cfg["command"],
                args=[expand_vars(a) for a in cfg.get("args", [])],
                env=env, cwd=cfg.get("cwd"))
            errlog = stack.enter_context(self.log_path.open("a", encoding="utf-8"))
            streams = await stack.enter_async_context(stdio_client(params, errlog=errlog))
        return streams[0], streams[1]

    async def _run_server(self, name: str, cfg: dict, ready: threading.Event) -> None:
        from mcp import ClientSession

        status = self.status[name]
        try:
            async with AsyncExitStack() as stack:
                read, write = await self._open_transport(stack, cfg)
                session = await stack.enter_async_context(
                    ClientSession(read, write, read_timeout_seconds=self.call_timeout))
                await session.initialize()
                listed = (await session.list_tools()).tools
                self._sessions[name] = session
                for tool in listed:
                    self._register(name, tool, confirm=cfg.get("confirm", True))
                status.tools = [t.name for t in listed]
                status.connected = True
                status.error = ""
                ready.set()
                await self._stop.wait()
        except Exception as exc:
            status.error = _describe(exc)
        finally:
            status.connected = False
            self._sessions.pop(name, None)
            for key in [k for k in self._tools if k.startswith(f"{name}__")]:
                self._tools.pop(key, None)
            ready.set()

    def _register(self, server: str, tool, confirm: bool) -> None:
        full_name = _SAFE_NAME.sub("_", f"{server}__{tool.name}")[:64]
        schema = tool.input_schema or {"type": "object", "properties": {}}
        description = (tool.description or tool.name).strip()[:600]
        self._tools[full_name] = Tool(
            full_name, f"[Conector {server}] {description}", schema,
            lambda _server=server, _tool=tool.name, **kwargs: self.call(_server, _tool, kwargs),
            needs_confirmation=confirm,
        )

    def call(self, server: str, tool: str, arguments: dict) -> str:
        session = self._sessions.get(server)
        if session is None or self._loop is None:
            return f"El conector '{server}' no está conectado."
        future = asyncio.run_coroutine_threadsafe(session.call_tool(tool, arguments), self._loop)
        result = future.result(timeout=self.call_timeout + 5)
        parts = []
        for item in getattr(result, "content", None) or []:
            kind = getattr(item, "type", "")
            if kind == "text":
                parts.append(item.text)
            elif kind == "resource" and hasattr(item.resource, "text"):
                parts.append(item.resource.text)
            else:
                parts.append(f"[contenido de tipo {kind or 'desconocido'}]")
        text = "\n".join(parts) or str(getattr(result, "structured_content", "") or "(sin resultado)")
        if getattr(result, "is_error", False):
            text = f"Error del conector: {text}"
        return text
