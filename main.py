"""Chat por terminal con tu IA.

Uso:
    python main.py                      # chat interactivo
    python main.py --pregunta "..."     # una sola pregunta
    python main.py --check              # comprobar conexión con el modelo
"""
import argparse
import sys
import uuid

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax

from mi_ia.agent import Agent
from mi_ia.config import get_settings
from mi_ia.llm import ChatLLM, LLMError
from mi_ia.memory import Memory
from mi_ia.tools import build_tools

console = Console()

HELP = """**Comandos**
- `/aprende <texto>` — enséñale algo que recordará siempre
- `/notas` — ver lo que ha aprendido
- `/bien` — la última respuesta fue buena (se usará para entrenar)
- `/mal` — la última respuesta fue mala
- `/corrige <respuesta correcta>` — corrige la última respuesta (se usará para entrenar)
- `/nuevo` — empezar una conversación nueva
- `/salir` — salir
"""

ICONS = {"web_search": "🔎 Buscando", "fetch_url": "🌐 Leyendo", "run_python": "🐍 Ejecutando código",
         "read_file": "📄 Leyendo archivo", "write_file": "💾 Guardando archivo",
         "list_files": "📁 Listando archivos"}


def on_event(tool: str, args: dict) -> None:
    detail = args.get("query") or args.get("url") or args.get("path") or ""
    console.print(f"[dim]{ICONS.get(tool, tool)} {detail}[/dim]")


def confirm(tool: str, args: dict) -> bool:
    if tool == "run_python":
        console.print(Panel(Syntax(args.get("code", ""), "python"), title="Código a ejecutar"))
    return Confirm.ask(f"¿Permitir {tool}?", default=False)


def build_agent() -> tuple[Agent, Memory]:
    s = get_settings()
    llm = ChatLLM(s.llm_base_url, s.llm_api_key, s.llm_model, s.llm_temperature, s.llm_timeout)
    memory = Memory(s.data_dir)
    agent = Agent(llm, build_tools(s), memory, name=s.ai_name, max_steps=s.max_tool_steps,
                  confirm=confirm, on_event=on_event)
    return agent, memory


def check() -> int:
    s = get_settings()
    llm = ChatLLM(s.llm_base_url, s.llm_api_key, s.llm_model, timeout=15)
    try:
        models = llm.list_models()
    except LLMError as exc:
        console.print(f"[red]✗ {exc}[/red]")
        return 1
    console.print(f"[green]✓ Conectado a {s.llm_base_url}[/green]")
    if s.llm_model in models:
        console.print(f"[green]✓ Modelo '{s.llm_model}' disponible[/green]")
        return 0
    console.print(f"[yellow]! El modelo '{s.llm_model}' no está. Disponibles: {', '.join(models) or 'ninguno'}")
    console.print(f"  Descárgalo con: ollama pull {s.llm_model}[/yellow]")
    return 1


def answer(agent: Agent, question: str) -> str | None:
    try:
        with console.status("Pensando...", spinner="dots"):
            reply = agent.ask(question)
    except LLMError as exc:
        console.print(f"[red]{exc}[/red]")
        return None
    console.print(Markdown(reply or "_(sin respuesta)_"))
    return reply


def chat() -> None:
    agent, memory = build_agent()
    session = uuid.uuid4().hex[:8]
    last_turn = None
    console.print(Panel(f"Hola, soy [bold]{agent.name}[/bold]. Escribe /ayuda para ver los comandos.",
                        style="cyan"))
    while True:
        try:
            text = console.input("\n[bold green]Tú ›[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        cmd, _, rest = text.partition(" ")
        if cmd in ("/salir", "/exit"):
            break
        if cmd == "/ayuda":
            console.print(Markdown(HELP))
        elif cmd == "/nuevo":
            agent.reset()
            console.print("[dim]Conversación nueva.[/dim]")
        elif cmd == "/aprende" and rest:
            memory.add_note(rest)
            console.print("[green]Aprendido.[/green]")
        elif cmd == "/notas":
            notes = memory.notes()
            console.print(Markdown("\n".join(f"- {n}" for n in notes) or "_Aún no he aprendido nada._"))
        elif cmd in ("/bien", "/mal", "/corrige"):
            if last_turn is None:
                console.print("[yellow]Todavía no hay ninguna respuesta que valorar.[/yellow]")
            elif cmd == "/corrige" and not rest:
                console.print("[yellow]Uso: /corrige <la respuesta correcta>[/yellow]")
            else:
                rating = {"/bien": "good", "/mal": "bad", "/corrige": "corrected"}[cmd]
                memory.rate(last_turn, rating, rest or None)
                console.print("[green]¡Gracias! Lo usaré para entrenar.[/green]")
        elif cmd.startswith("/"):
            console.print("[yellow]Comando desconocido. Escribe /ayuda.[/yellow]")
        else:
            reply = answer(agent, text)
            if reply is not None:
                last_turn = memory.log_turn(session, text, reply, agent.last_tools)
    console.print("[dim]¡Hasta luego![/dim]")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Tu propia IA")
    parser.add_argument("--check", action="store_true", help="comprobar conexión con el modelo")
    parser.add_argument("--pregunta", help="hacer una sola pregunta y salir")
    args = parser.parse_args()
    if args.check:
        return check()
    if args.pregunta:
        agent, memory = build_agent()
        reply = answer(agent, args.pregunta)
        if reply is not None:
            memory.log_turn("cli", args.pregunta, reply, agent.last_tools)
        return 0 if reply is not None else 1
    chat()
    return 0


if __name__ == "__main__":
    sys.exit(main())
