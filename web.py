"""Abre la interfaz web de tu IA.

Uso:  python web.py      y se abrirá http://127.0.0.1:8000 en tu navegador.
"""
import threading
import webbrowser

import uvicorn

from mi_ia.config import get_settings


def main() -> None:
    port = get_settings().web_port
    url = f"http://127.0.0.1:{port}"
    print(f"Mi IA está en {url}  (Ctrl+C para parar)")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    # 127.0.0.1: solo accesible desde tu PC, no desde la red
    uvicorn.run("mi_ia.web.server:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
