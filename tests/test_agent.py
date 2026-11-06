import json

from mi_ia.agent import Agent
from mi_ia.memory import Memory
from mi_ia.tools import Tool


class FakeLLM:
    """Simula un modelo: devuelve respuestas preparadas y guarda lo que recibe."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages, tools=None):
        self.calls.append(messages)
        return self.replies.pop(0)


def echo_tool(**kw):
    return Tool("echo", "repite", {"type": "object", "properties": {}}, lambda text: f"eco:{text}", **kw)


def tool_call(name, args):
    return {"content": "", "tool_calls": [
        {"id": "c1", "function": {"name": name, "arguments": json.dumps(args)}}]}


def test_agent_uses_tool_then_answers(tmp_path):
    llm = FakeLLM([tool_call("echo", {"text": "hola"}), {"content": "listo"}])
    agent = Agent(llm, {"echo": echo_tool()}, Memory(tmp_path))
    assert agent.ask("di hola") == "listo"
    assert agent.last_tools == ["echo"]
    assert llm.calls[1][-1] == {"role": "tool", "tool_call_id": "c1", "content": "eco:hola"}


def test_agent_parses_tool_call_written_as_text(tmp_path):
    text_call = {"content": '```json\n{"name": "echo", "arguments": {"text": "x"}}\n```'}
    llm = FakeLLM([text_call, {"content": "ok"}])
    agent = Agent(llm, {"echo": echo_tool()}, Memory(tmp_path))
    assert agent.ask("?") == "ok"
    assert agent.last_tools == ["echo"]


def test_agent_unwraps_schema_copied_as_arguments(tmp_path):
    copied = {"text": {"type": "string", "description": "Pedro Sanchez"}}
    llm = FakeLLM([tool_call("echo", copied), {"content": "ok"}])
    Agent(llm, {"echo": echo_tool()}, Memory(tmp_path)).ask("?")
    assert llm.calls[1][-1]["content"] == "eco:Pedro Sanchez"


def test_agent_breaks_repeated_tool_loop(tmp_path):
    runs = []
    tool = Tool("echo", "", {"type": "object", "properties": {}},
                lambda text: runs.append(text) or "eco")
    llm = FakeLLM([tool_call("echo", {"text": "x"})] * 3 + [{"content": "respuesta final"}])
    agent = Agent(llm, {"echo": tool}, Memory(tmp_path), max_steps=6)
    assert agent.ask("?") == "respuesta final"
    assert runs == ["x"]          # la herramienta solo se ejecutó una vez
    assert len(llm.calls) == 4    # 3 intentos + respuesta forzada


def test_agent_respects_confirmation(tmp_path):
    llm = FakeLLM([tool_call("echo", {"text": "x"}), {"content": "fin"}])
    agent = Agent(llm, {"echo": echo_tool(needs_confirmation=True)}, Memory(tmp_path),
                  confirm=lambda tool, args: False)
    agent.ask("?")
    assert "no ha permitido" in llm.calls[1][-1]["content"]


def test_agent_redacts_tool_output(tmp_path):
    leak = Tool("leak", "", {"type": "object", "properties": {}},
                lambda: "clave sk-proj-a8F3kL9mQ2xR7vT1nB5cW4zY6pD0sJ")
    llm = FakeLLM([tool_call("leak", {}), {"content": "fin"}])
    Agent(llm, {"leak": leak}, Memory(tmp_path)).ask("?")
    assert "sk-proj" not in llm.calls[1][-1]["content"]


def test_agent_stops_after_max_steps(tmp_path):
    llm = FakeLLM([tool_call("echo", {"text": "x"})] * 2 + [{"content": "resumen"}])
    agent = Agent(llm, {"echo": echo_tool()}, Memory(tmp_path), max_steps=2)
    assert agent.ask("?") == "resumen"


def test_memory_notes_are_used_in_prompt(tmp_path):
    memory = Memory(tmp_path)
    memory.add_note("El usuario programa en Python y usa Django")
    llm = FakeLLM([{"content": "ok"}])
    Agent(llm, {}, memory).ask("¿Cómo creo un modelo en Django?")
    assert "Django" in llm.calls[0][0]["content"]
