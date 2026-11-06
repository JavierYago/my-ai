"""Construye el dataset de entrenamiento.

Junta:
  1. Los ejemplos escritos a mano en training/seed/*.md (y *.jsonl)
  2. Las respuestas que marcaste con /bien en el chat
  3. Las correcciones que hiciste con /corrige

Todo pasa por el filtro de secretos antes de guardarse en training/dataset.jsonl.

Uso:  python training/build_dataset.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from yunque.config import get_settings  # noqa: E402
from yunque.memory import Memory  # noqa: E402
from yunque.prompts import build_system_prompt  # noqa: E402
from yunque.security import redact  # noqa: E402

SEED_DIR = ROOT / "training" / "seed"
OUTPUT = ROOT / "training" / "dataset.jsonl"
_ROLE = re.compile(r"^>>> (usuario|asistente)\s*$", re.MULTILINE)
_ROLES = {"usuario": "user", "asistente": "assistant"}


def parse_markdown(text: str) -> list[list[dict]]:
    """Convierte el formato '=== ejemplo === / >>> usuario / >>> asistente' en conversaciones."""
    conversations = []
    for block in text.split("=== ejemplo ===")[1:]:
        parts = _ROLE.split(block)
        # parts = [texto previo, rol, contenido, rol, contenido, ...]
        messages = [
            {"role": _ROLES[role], "content": content.strip()}
            for role, content in zip(parts[1::2], parts[2::2])
            if content.strip()
        ]
        if messages and messages[-1]["role"] == "assistant":
            conversations.append(messages)
    return conversations


def load_seed(seed_dir: Path) -> list[list[dict]]:
    conversations = []
    for path in sorted(seed_dir.glob("*.md")):
        conversations += parse_markdown(path.read_text(encoding="utf-8"))
    for path in sorted(seed_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8") as f:
            conversations += [json.loads(line)["messages"] for line in f if line.strip()]
    return conversations


def load_feedback(memory: Memory) -> list[list[dict]]:
    turns = {t["id"]: t for t in memory.turns()}
    latest = {}  # si valoraste dos veces la misma respuesta, cuenta la última
    for fb in memory.feedback():
        latest[fb["turn"]] = fb
    conversations = []
    for turn_id, fb in latest.items():
        turn = turns.get(turn_id)
        if turn is None or fb["rating"] == "bad":
            continue
        answer = fb.get("correction") if fb["rating"] == "corrected" else turn["answer"]
        if answer:
            conversations.append([{"role": "user", "content": turn["question"]},
                                  {"role": "assistant", "content": answer}])
    return conversations


def build(seed_dir: Path, memory: Memory, output: Path, ai_name: str) -> int:
    system = build_system_prompt(ai_name, [])
    seen = set()
    count = 0
    with output.open("w", encoding="utf-8") as f:
        for conv in load_seed(seed_dir) + load_feedback(memory):
            clean = [{"role": m["role"],
                      "content": redact(m["content"].replace("Yunque", ai_name))}
                     for m in conv]
            key = json.dumps(clean, ensure_ascii=False)
            if key in seen:
                continue
            seen.add(key)
            record = {"messages": [{"role": "system", "content": system}, *clean]}
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    settings = get_settings()
    n = build(SEED_DIR, Memory(settings.data_dir), OUTPUT, settings.ai_name)
    print(f"Dataset creado: {OUTPUT.relative_to(ROOT)} ({n} ejemplos)")
    if n < 50:
        print("Consejo: con menos de 50-100 ejemplos el efecto del entrenamiento será pequeño. "
              "Usa la IA, valora con /bien y /corrige, y añade ejemplos en training/seed/.")


if __name__ == "__main__":
    main()
