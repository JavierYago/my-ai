"""Crea el Modelfile de Ollama para tu modelo entrenado.

Copia la plantilla de chat del modelo base (para que entienda herramientas) y
apunta al archivo .gguf que generaste.

Uso:
    python training/make_modelfile.py training/mi-ia.gguf --base qwen2.5-coder:1.5b
    ollama create mi-ia -f training/Modelfile
"""
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("gguf", help="ruta al archivo .gguf")
    p.add_argument("--base", default="qwen2.5-coder:1.5b", help="modelo de Ollama del que partiste")
    p.add_argument("--name", default="mi-ia")
    args = p.parse_args()

    gguf = Path(args.gguf).resolve()
    if not gguf.is_file():
        raise SystemExit(f"No existe {gguf}")

    subprocess.run(["ollama", "pull", args.base], check=True)
    base_modelfile = subprocess.run(["ollama", "show", args.base, "--modelfile"], check=True,
                                    capture_output=True, text=True, encoding="utf-8").stdout
    lines = [f"FROM {gguf.as_posix()}" if line.startswith("FROM ") else line
             for line in base_modelfile.splitlines()]
    out = ROOT / "training" / "Modelfile"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Creado {out}")
    print(f"Ahora ejecuta:  ollama create {args.name} -f training/Modelfile")
    print(f"Y en tu .env pon:  LLM_MODEL={args.name}")


if __name__ == "__main__":
    main()
