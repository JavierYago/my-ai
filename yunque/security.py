"""Utilidades de seguridad: ocultar secretos, rutas seguras y URLs públicas."""
import ipaddress
import os
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

REDACTED = "[REDACTADO]"

# Formatos conocidos de claves de servicios populares
_KEY_PATTERNS = [
    re.compile(p)
    for p in (
        r"sk-ant-[A-Za-z0-9_\-]{20,}",
        r"sk-[A-Za-z0-9_\-]{20,}",
        r"gh[pousr]_[A-Za-z0-9]{30,}",
        r"github_pat_[A-Za-z0-9_]{40,}",
        r"AKIA[0-9A-Z]{16}",
        r"AIza[0-9A-Za-z_\-]{35}",
        r"xox[abprs]-[A-Za-z0-9\-]{10,}",
        r"tvly-[A-Za-z0-9_\-]{20,}",
        r"gsk_[A-Za-z0-9]{20,}",
        r"hf_[A-Za-z0-9]{30,}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----",
    )
]

# Asignaciones tipo API_KEY=valor o "password": "valor"
_ASSIGNMENT = re.compile(
    r"(?i)\b([\w\-]*(?:api[_\-]?key|secret|token|password|passwd|pwd)[\w\-]*)"
    r"(['\"]?\s*[:=]\s*['\"]?)([^\s'\",;]+)"
)
_PLACEHOLDER = re.compile(
    r"(?i)^(tu_|your|<|\[|x{3,}|\*+|\.\.\.|changeme|example|ejemplo|placeholder|ollama$)"
)
_DOTTED_NAME = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)+$")
_SENSITIVE_ENV = re.compile(r"(?i)(key|token|secret|password|passwd)")


def _keep_value(value: str) -> bool:
    """True si el valor parece código o un ejemplo, no un secreto real."""
    return (
        len(value) < 6
        or _PLACEHOLDER.match(value) is not None
        or "(" in value
        or value.startswith(("os.", "process.", "$", "env.", "import."))
        or _DOTTED_NAME.match(value) is not None
    )


def redact(text: str) -> str:
    """Oculta claves y contraseñas de un texto antes de mostrarlo o guardarlo."""
    if not text:
        return text
    # 1) Valores reales de variables de entorno sensibles (las del .env)
    for name, value in os.environ.items():
        if _SENSITIVE_ENV.search(name) and value and len(value) >= 8:
            text = text.replace(value, REDACTED)
    # 2) Formatos de clave conocidos
    for pattern in _KEY_PATTERNS:
        text = pattern.sub(REDACTED, text)

    # 3) Asignaciones del tipo PASSWORD=algo
    def _sub(m: re.Match) -> str:
        value = m.group(3)
        if _keep_value(value):
            return m.group(0)
        return f"{m.group(1)}{m.group(2)}{REDACTED}"

    return _ASSIGNMENT.sub(_sub, text)


_BLOCKED_NAMES = re.compile(
    r"(?i)^(\.env(\..*)?|.*\.pem|.*\.key|.*\.p12|id_rsa.*|id_ed25519.*|credentials.*)$"
)


def is_blocked_file(path: Path) -> bool:
    name = path.name
    if name == ".env.example":
        return False
    return _BLOCKED_NAMES.match(name) is not None


def safe_path(base: Path, relative: str) -> Path:
    """Devuelve una ruta dentro de `base`; lanza error si intenta salirse."""
    base = base.resolve()
    target = (base / relative).resolve()
    if target != base and base not in target.parents:
        raise PermissionError(f"Ruta fuera de la carpeta permitida: {relative}")
    if is_blocked_file(target):
        raise PermissionError(f"Acceso denegado a archivo sensible: {target.name}")
    return target


def is_public_url(url: str) -> bool:
    """Evita que la IA acceda a tu red local o a servicios internos (SSRF)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except (socket.gaierror, UnicodeError):
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global or ip.is_multicast:
            return False
    return True
