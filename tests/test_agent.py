import json

from yunque.agent import Agent
from yunque.memory import Memory
from yunque.tools import Tool


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


def test_agent_collects_generated_media(tmp_path):
    media = {"kind": "image", "path": "generated/a.jpg", "alt": "gato"}
    tool = Tool("img", "", {"type": "object", "properties": {}},
                lambda: {"text": "imagen lista", "media": media})
    events = []
    llm = FakeLLM([tool_call("img", {}), {"content": "aquí la tienes"}])
    agent = Agent(llm, {"img": tool}, Memory(tmp_path), on_event=lambda t, a: events.append(t))
    agent.ask("dibuja un gato")
    assert agent.last_media == [media]
    assert "_media" in events
    assert llm.calls[1][-1]["content"] == "imagen lista"


def test_voice_mode_only_offers_web_tools(tmp_path):
    tools = {"web_search": echo_tool(), "run_python": echo_tool(needs_confirmation=True),
             "generate_image": echo_tool()}
    for name, t in tools.items():
        t.name = name
    agent = Agent(FakeLLM([]), tools, Memory(tmp_path))
    _, voice_schemas = agent.prompt_and_tools(voice=True)
    _, text_schemas = agent.prompt_and_tools()
    assert [s["function"]["name"] for s in voice_schemas] == ["web_search"]
    assert len(text_schemas) == 3


def test_skill_called_as_tool_is_redirected_to_use_skill(tmp_path):
    class Skills:
        def summary(self):
            return [("explicar", "Explicar cosas")]

    loaded = []
    use_skill = Tool("use_skill", "", {"type": "object", "properties": {}},
                     lambda name: loaded.append(name) or "instrucciones")
    text_call = {"content": '{"name": "explicar", "arguments": {"text": "hola"}}'}
    llm = FakeLLM([text_call, {"content": "listo"}])
    agent = Agent(llm, {"use_skill": use_skill}, Memory(tmp_path), skills=Skills())
    assert agent.ask("?") == "listo"
    assert loaded == ["explicar"]


def test_unknown_tool_lists_available_tools(tmp_path):
    llm = FakeLLM([{"content": '{"name": "volar", "arguments": {}}'}, {"content": "ok"}])
    Agent(llm, {"echo": echo_tool()}, Memory(tmp_path)).ask("?")
    assert "no existe" in llm.calls[1][-1]["content"] and "echo" in llm.calls[1][-1]["content"]


def test_plain_json_answer_is_not_a_tool_call(tmp_path):
    llm = FakeLLM([{"content": '{"name": "Juan", "edad": 30}'}])
    assert Agent(llm, {}, Memory(tmp_path)).ask("dame un json") == '{"name": "Juan", "edad": 30}'


def test_tool_failure_notice_reaches_user_even_if_model_refuses(tmp_path):
    tool = Tool("music", "", {"type": "object", "properties": {}},
                lambda: {"text": "fallo", "notice": "Hace falta Pollen de pago."})
    llm = FakeLLM([tool_call("music", {}), {"content": "Lo siento, pero no puedo ayudarte con eso."}])
    answer = Agent(llm, {"music": tool}, Memory(tmp_path)).ask("hazme música")
    assert answer == "⚠️ Hace falta Pollen de pago."


def test_long_answer_keeps_text_and_adds_notice(tmp_path):
    tool = Tool("music", "", {"type": "object", "properties": {}},
                lambda: {"text": "fallo", "notice": "Hace falta Pollen de pago."})
    long_answer = "Te explico varias alternativas gratuitas para conseguir música. " * 4
    llm = FakeLLM([tool_call("music", {}), {"content": long_answer}])
    answer = Agent(llm, {"music": tool}, Memory(tmp_path)).ask("hazme música")
    assert answer.startswith(long_answer) and answer.endswith("⚠️ Hace falta Pollen de pago.")


def test_memory_notes_are_used_in_prompt(tmp_path):
    memory = Memory(tmp_path)
    memory.add_note("El usuario programa en Python y usa Django")
    llm = FakeLLM([{"content": "ok"}])
    Agent(llm, {}, memory).ask("¿Cómo creo un modelo en Django?")
    assert "Django" in llm.calls[0][0]["content"]
