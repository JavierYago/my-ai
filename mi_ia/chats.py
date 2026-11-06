"""Guarda las conversaciones de la web (una por archivo en data/chats/)."""
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from .security import redact

_ID = re.compile(r"^[a-f0-9]{12}$")


class ChatStore:
    def __init__(self, data_dir: Path):
        self.dir = data_dir / "chats"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, chat_id: str) -> Path:
        # Solo se aceptan ids generados por nosotros: evita rutas tipo "../../"
        if not _ID.match(chat_id):
            raise KeyError(chat_id)
        return self.dir / f"{chat_id}.json"

    def create(self) -> dict:
        chat = {"id": uuid.uuid4().hex[:12], "title": "Nueva conversación",
                "updated": _now(), "messages": []}
        self.save(chat)
        return chat

    def get(self, chat_id: str) -> dict:
        path = self._path(chat_id)
        if not path.exists():
            raise KeyError(chat_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def save(self, chat: dict) -> None:
        chat["updated"] = _now()
        self._path(chat["id"]).write_text(json.dumps(chat, ensure_ascii=False, indent=1),
                                          encoding="utf-8")

    def delete(self, chat_id: str) -> None:
        self._path(chat_id).unlink(missing_ok=True)

    def all(self) -> list[dict]:
        chats = []
        for path in self.dir.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            chats.append({"id": data["id"], "title": data["title"], "updated": data["updated"]})
        return sorted(chats, key=lambda c: c["updated"], reverse=True)

    def add_turn(self, chat: dict, question: str, answer: str, turn_id: str,
                 tools: list[str]) -> None:
        if not chat["messages"]:
            title = " ".join(question.split())
            chat["title"] = redact(title[:60] + ("…" if len(title) > 60 else ""))
        chat["messages"] += [
            {"role": "user", "content": redact(question)},
            {"role": "assistant", "content": redact(answer), "turn_id": turn_id, "tools": tools},
        ]
        self.save(chat)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
