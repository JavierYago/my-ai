"""Lectura y escritura de archivos, limitadas a la carpeta workspace."""
from pathlib import Path

from ..security import is_blocked_file, safe_path

MAX_READ = 20_000


def list_files(workspace: Path, path: str = ".") -> str:
    folder = safe_path(workspace, path)
    if not folder.is_dir():
        return f"No existe la carpeta: {path}"
    items = []
    for p in sorted(folder.rglob("*")):
        if p.is_file() and not is_blocked_file(p) and len(items) < 200:
            items.append(str(p.relative_to(workspace)).replace("\\", "/"))
    return "\n".join(items) or "(carpeta vacía)"


def read_file(workspace: Path, path: str) -> str:
    target = safe_path(workspace, path)
    if not target.is_file():
        return f"No existe el archivo: {path}"
    text = target.read_text(encoding="utf-8", errors="replace")
    return text[:MAX_READ] + ("\n[...recortado]" if len(text) > MAX_READ else "")


def write_file(workspace: Path, path: str, content: str) -> str:
    target = safe_path(workspace, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Guardado: workspace/{target.relative_to(workspace.resolve()).as_posix()} ({len(content)} caracteres)"
