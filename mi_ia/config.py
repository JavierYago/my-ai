"""Configuración: todo se lee del archivo .env, nunca se escribe en el código."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "si", "sí", "yes")


@dataclass(frozen=True)
class Settings:
    ai_name: str
    llm_base_url: str
    llm_model: str
    llm_temperature: float
    llm_timeout: float
    max_tool_steps: int
    confirm_code: bool
    code_timeout: int
    data_dir: Path
    workspace_dir: Path
    web_port: int = 8000
    # repr=False: las claves nunca aparecen al imprimir la configuración
    llm_api_key: str = field(default="", repr=False)
    tavily_api_key: str = field(default="", repr=False)


def get_settings() -> Settings:
    data_dir = ROOT / "data"
    workspace_dir = ROOT / "workspace"
    data_dir.mkdir(exist_ok=True)
    workspace_dir.mkdir(exist_ok=True)
    return Settings(
        ai_name=os.getenv("AI_NAME", "Mi IA"),
        llm_base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/"),
        llm_model=os.getenv("LLM_MODEL", "qwen2.5-coder:3b"),
        llm_temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
        llm_timeout=float(os.getenv("LLM_TIMEOUT", "300")),
        max_tool_steps=int(os.getenv("MAX_TOOL_STEPS", "6")),
        confirm_code=_bool("CONFIRM_CODE", True),
        code_timeout=int(os.getenv("CODE_TIMEOUT", "20")),
        data_dir=data_dir,
        workspace_dir=workspace_dir,
        web_port=int(os.getenv("WEB_PORT", "8000")),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        tavily_api_key=os.getenv("TAVILY_API_KEY", ""),
    )
