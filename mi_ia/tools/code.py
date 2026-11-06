"""Ejecución de código Python en un proceso aparte, sin acceso a tus claves."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

MAX_OUTPUT = 6_000

# Solo se pasan estas variables al proceso: así el código no puede leer las claves del .env
_SAFE_ENV_VARS = ("PATH", "PATHEXT", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP",
                  "HOME", "USERPROFILE", "LANG", "WINDIR")


def run_python(code: str, workspace: Path, timeout: int = 20) -> str:
    env = {k: os.environ[k] for k in _SAFE_ENV_VARS if k in os.environ}
    env["PYTHONIOENCODING"] = "utf-8"
    with tempfile.NamedTemporaryFile("w", suffix=".py", dir=workspace,
                                     delete=False, encoding="utf-8") as f:
        f.write(code)
        script = Path(f.name)
    try:
        proc = subprocess.run(
            [sys.executable, "-I", str(script)],
            cwd=workspace, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        out = proc.stdout
        if proc.stderr:
            out += f"\n[stderr]\n{proc.stderr}"
        out = out.strip() or "(sin salida)"
        if proc.returncode != 0:
            out = f"[código de salida {proc.returncode}]\n{out}"
    except subprocess.TimeoutExpired:
        out = f"Tiempo agotado ({timeout} s). ¿Hay un bucle infinito o espera de input()?"
    finally:
        script.unlink(missing_ok=True)
    return out[:MAX_OUTPUT]
