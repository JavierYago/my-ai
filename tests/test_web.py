import json

import pytest
from fastapi.testclient import TestClient

from mi_ia.chats import ChatStore
from mi_ia.memory import Memory
from mi_ia.web import server


class StreamingFakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)

    def chat_stream(self, messages, tools=None, on_token=None):
        reply = self.replies.pop(0)
        for word in (reply.get("content") or "").split(" "):
            on_token(word + " ")
        return reply


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "store", ChatStore(tmp_path))
    monkeypatch.setattr(server, "memory", Memory(tmp_path))
    port = server.settings.web_port
    return TestClient(server.app, base_url=f"http://127.0.0.1:{port}")


def events(response):
    return [json.loads(line) for line in response.text.splitlines() if line]


def test_index_and_security_headers(client):
    r = client.get("/")
    assert r.status_code == 200 and "Mi IA" in r.text
    assert "default-src 'self'" in r.headers["content-security-policy"]


def test_rejects_foreign_host_and_origin(client):
    assert client.get("/api/chats", headers={"host": "evil.com"}).status_code == 403
    r = client.post("/api/chats", headers={"origin": "https://evil.com"})
    assert r.status_code == 403


def test_rejects_bad_chat_ids(client):
    assert client.get("/api/chats/..%2F..%2F.env").status_code == 404
    assert client.get("/api/chats/zzz").status_code == 404


def test_chat_flow_with_streaming(client, monkeypatch):
    monkeypatch.setattr(server, "llm", StreamingFakeLLM([{"content": "Hola mundo"}]))
    chat = client.post("/api/chats").json()
    r = client.post(f"/api/chats/{chat['id']}/messages", json={"text": "di hola"})
    evs = events(r)
    tokens = "".join(e["text"] for e in evs if e["type"] == "token")
    done = evs[-1]
    assert tokens.strip() == "Hola mundo"
    assert done["type"] == "done" and done["title"] == "di hola"

    saved = client.get(f"/api/chats/{chat['id']}").json()
    assert [m["role"] for m in saved["messages"]] == ["user", "assistant"]
    assert client.get("/api/chats").json()[0]["id"] == chat["id"]

    ok = client.post("/api/feedback", json={"turn_id": done["turn_id"], "rating": "good"})
    assert ok.status_code == 200
    bad = client.post("/api/feedback", json={"turn_id": done["turn_id"], "rating": "hack"})
    assert bad.status_code == 422


def test_notes(client):
    assert client.post("/api/notes", json={"text": "Uso Django"}).json() == ["Uso Django"]
