"""Herramientas que la IA puede usar: web, código, archivos, imágenes, audio y habilidades."""
from dataclasses import dataclass
from typing import Callable

from ..config import Settings
from . import files, media, web
from .code import run_python


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    # Devuelve texto, o {"text": ..., "media": {...}} si genera una imagen o un audio
    func: Callable[..., str | dict]
    needs_confirmation: bool = False

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def _params(required: list[str], **props: dict) -> dict:
    return {"type": "object", "properties": props, "required": required}


def build_tools(settings: Settings, voice=None, skills=None) -> dict[str, Tool]:
    ws = settings.workspace_dir
    tools = [
        Tool(
            "web_search",
            "Busca en internet. Úsala para hechos recientes, datos que cambian o si no estás seguro.",
            _params(["query"], query={"type": "string", "description": "Qué buscar"}),
            lambda query: web.web_search(query, settings.tavily_api_key),
        ),
        Tool(
            "fetch_url",
            "Descarga una página web y devuelve su texto. Úsala para leer los resultados de web_search.",
            _params(["url"], url={"type": "string", "description": "URL http(s) pública"}),
            lambda url: web.fetch_url(url),
        ),
        Tool(
            "run_python",
            "Ejecuta código Python y devuelve lo que imprime. Úsala para probar código o calcular.",
            _params(["code"], code={"type": "string", "description": "Código Python completo"}),
            lambda code: run_python(code, ws, settings.code_timeout),
            needs_confirmation=settings.confirm_code,
        ),
        Tool(
            "list_files",
            "Lista los archivos de la carpeta de trabajo (workspace).",
            _params([], path={"type": "string", "description": "Subcarpeta (opcional)"}),
            lambda path=".": files.list_files(ws, path),
        ),
        Tool(
            "read_file",
            "Lee un archivo de la carpeta de trabajo (workspace).",
            _params(["path"], path={"type": "string"}),
            lambda path: files.read_file(ws, path),
        ),
        Tool(
            "write_file",
            "Crea o sobrescribe un archivo en la carpeta de trabajo (workspace).",
            _params(["path", "content"], path={"type": "string"}, content={"type": "string"}),
            lambda path, content: files.write_file(ws, path, content),
        ),
        Tool(
            "generate_image",
            "Genera una imagen a partir de una descripción. El prompt debe ir en inglés y detallado.",
            _params(["prompt"],
                    prompt={"type": "string", "description": "Descripción detallada en inglés"},
                    width={"type": "integer", "description": "Ancho en píxeles (1024 por defecto)"},
                    height={"type": "integer", "description": "Alto en píxeles (1024 por defecto)"}),
            lambda prompt, width=1024, height=1024: media.generate_image(
                prompt, ws, settings.pollinations_api_key, settings.image_model, width, height),
        ),
        Tool(
            "generate_music",
            "Genera música o efectos de sonido a partir de una descripción (mejor en inglés).",
            _params(["prompt"], prompt={"type": "string", "description": "Estilo, instrumentos, ambiente"}),
            lambda prompt: media.generate_music(
                prompt, ws, settings.pollinations_api_key, settings.music_model),
        ),
    ]
    if voice is not None:
        tools.append(Tool(
            "generate_speech",
            "Convierte un texto en un archivo de audio con voz (narraciones, mensajes leídos).",
            _params(["text"], text={"type": "string", "description": "Texto que se leerá en voz alta"}),
            lambda text: media.generate_speech(text, ws, voice),
        ))
    if skills is not None:
        tools.append(Tool(
            "use_skill",
            "Carga las instrucciones detalladas de una de tus habilidades.",
            _params(["name"], name={"type": "string", "description": "Nombre de la habilidad"}),
            lambda name: skills.load(name),
        ))
    return {t.name: t for t in tools}
