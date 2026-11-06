"""Memoria de la IA: notas aprendidas, historial y valoraciones (datos de entrenamiento)."""
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from .security import redact

_WORD = re.compile(r"\w{3,}", re.UNICODE)


def _words(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text)}


def _append(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class Memory:
    def __init__(self, data_dir: Path):
        self.notes_path = data_dir / "notes.jsonl"
        self.turns_path = data_dir / "conversations.jsonl"
        self.feedback_path = data_dir / "feedback.jsonl"

    # --- Notas: lo que le enseñas con /aprende ---
    def add_note(self, text: str) -> None:
        _append(self.notes_path, {"text": redact(text.strip()), "date": _now()})

    def notes(self) -> list[str]:
        return [n["text"] for n in _read(self.notes_path)]

    def relevant_notes(self, query: str, k: int = 5) -> list[str]:
        """Devuelve las notas que más palabras comparten con la pregunta."""
        q = _words(query)
        scored = [(len(q & _words(n)), n) for n in self.notes()]
        return [n for score, n in sorted(scored, reverse=True)[:k] if score > 0]

    # --- Historial: cada pregunta y respuesta (sin secretos) ---
    def log_turn(self, session: str, question: str, answer: str, tools: list[str]) -> str:
        turn_id = uuid.uuid4().hex[:12]
        _append(self.turns_path, {
            "id": turn_id, "session": session, "date": _now(), "tools": tools,
            "question": redact(question), "answer": redact(answer),
        })
        return turn_id

    def turns(self) -> list[dict]:
        return _read(self.turns_path)

    # --- Valoraciones: /bien, /mal, /corrige ---
    def rate(self, turn_id: str, rating: str, correction: str | None = None) -> None:
        record = {"turn": turn_id, "rating": rating, "date": _now()}
        if correction:
            record["correction"] = redact(correction)
        _append(self.feedback_path, record)

    def feedback(self) -> list[dict]:
        return _read(self.feedback_path)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
