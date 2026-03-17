import shutil
import signal
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.text import Text
from rich.align import Align
from rich import box

from agent import Agent
from background import BackgroundWorker
from config import APP_NAME, BACKUP_DIR, CONFIG, MODEL
from db import MemoryDB
from llm import AnthropicClient
from state import AgentState
from tools import ToolRunner
from utils import append_log


console = Console()

FACES = {
    "happy": "^_^",
    "excited": "^ω^",
    "curious": "o_O",
    "sad": ";_;",
    "tired": "-_-",
    "angry": ">_<",
    "think": "¬_¬",
    "work": "@_@",
    "love": "♥‿♥",
    "shock": "O_O",
    "smug": "ʘ‿ʘ",
}

ARIA_LOGO = r"""
 ░█████╗░██████╗░██╗░█████╗░
 ██╔══██╗██╔══██╗██║██╔══██╗
 ███████║██████╔╝██║███████║
 ██╔══██║██╔══██╗██║██╔══██║
 ██║░░██║██║░░██║██║██║░░██║
 ╚═╝░░╚═╝╚═╝░░╚═╝╚═╝╚═╝░░╚═╝
"""

db = MemoryDB()
state = AgentState()
state.session_id = db.start_session()
llm = AnthropicClient()
tools = ToolRunner(state, db)
agent = Agent(llm, db, state, tools)
bg = BackgroundWorker(agent, state, db)


def backup_self() -> None:
    src = Path(__file__).resolve()
    dst = BACKUP_DIR / f"aria_v9_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
    shutil.copy2(src, dst)

    backups = sorted(BACKUP_DIR.glob("aria_v9_*.py"))
    for old in backups[:-20]:
        try:
            old.unlink()
        except Exception:
            pass


def render_status() -> Panel:
    face = FACES.get(state.face, "^_^")
    mood_style = "bold bright_green" if state.mood >= 70 else "bold yellow" if state.mood >= 40 else "bold red"

    face_art = Text()
    face_art.append("╭─────╮\n", style="dim")
    face_art.append(f"│ {face} │\n", style=mood_style)
    face_art.append("╰─────╯", style="dim")

    title = (
        f"[bold cyan]{APP_NAME}[/bold cyan]  "
        f"[dim]session:{state.session_id} "
        f"cmd:{state.commands_run} "
        f"bg:{state.background_cycles} "
        f"db_sessions:{db.sessions_count()} "
        f"facts:{db.facts_count()}[/dim]"
    )
    subtitle = f"[dim]💭 {state.last_thought[:80]}[/dim]"

    return Panel(
        Align.center(face_art),
        title=title,
        subtitle=subtitle,
        border_style="cyan",
        padding=(0, 2),
    )


def print_help() -> None:
    t = Table(box=box.SIMPLE, show_header=False, border_style="dim")
    t.add_column(style="yellow", width=22)
    t.add_column(style="dim")

    rows = [
        ("пока", "выход"),
        ("статус", "показать статус"),
        ("память", "статистика памяти"),
        ("факты", "последние важные факты"),
        ("найди [текст]", "поиск по фактам"),
        ("заметки", "последние заметки"),
        ("фон", "вкл/выкл фон"),
        ("помощь", "справка"),
    ]
    for r in rows:
        t.add_row(*r)

    console.print(Panel(t, title="[bold]Команды[/bold]", border_style="dim"))


def command_memory() -> None:
    table = Table(box=box.ROUNDED, border_style="cyan", title="Память")
    table.add_column("Параметр", style="dim")
    table.add_column("Значение", style="cyan")
    table.add_row("Сессий", str(db.sessions_count()))
    table.add_row("Фактов", str(db.facts_count()))
    table.add_row("Команд", str(state.commands_run))
    table.add_row("Последняя мысль", state.last_thought[:80])
    console.print(table)


def command_facts() -> None:
    facts = db.search_facts("", limit=15)
    if not facts:
        console.print("[dim]Фактов пока нет.[/dim]")
        return
    txt = "\n".join(f"• {f['fact']}" for f in facts)
    console.print(Panel(txt, title="Последние факты", border_style="magenta"))


def command_search(query: str) -> None:
    rows = db.search_facts(query, limit=20)
    if not rows:
        console.print(f"[dim]Ничего не найдено по '{query}'.[/dim]")
        return
    txt = "\n".join(f"• {r['fact']}" for r in rows)
    console.print(Panel(txt, title=f"Найдено: {query}", border_style="cyan"))


def command_notes() -> None:
    rows = db.recent_notes(20)
    if not rows:
        console.print("[dim]Заметок пока нет.[/dim]")
        return
    txt = "\n".join(f"[{r['created_at']}] {r['note']}" for r in reversed(rows))
    console.print(Panel(txt, title="Заметки", border_style="green"))


def command_toggle_bg() -> None:
    CONFIG["background_enabled"] = not CONFIG["background_enabled"]
    if CONFIG["background_enabled"]:
        bg.start()
        console.print("[green]Фон включен.[/green]")
    else:
        bg.stop()
        console.print("[yellow]Фон выключен.[/yellow]")


def graceful_shutdown(*args) -> None:
    try:
        bg.stop()
        summary = (
            f"energy={state.energy}, mood={state.mood}, "
            f"commands={state.commands_run}, thought={state.last_thought[:100]}"
        )
        db.end_session(state.session_id, summary=summary)
        append_log("shutdown")
    finally:
        raise SystemExit(0)


def boot() -> None:
    console.clear()
    logo = Text(ARIA_LOGO, style="bold cyan")
    console.print(Panel(Align.center(logo), border_style="dim cyan", padding=(0, 4)))
    console.print()
    console.print(f"  [cyan]▸ MODEL:[/cyan] {MODEL}")
    console.print(f"  [cyan]▸ OWNER:[/cyan] {CONFIG['owner_name']}")
    console.print(f"  [cyan]▸ BACKGROUND:[/cyan] {'ON' if CONFIG['background_enabled'] else 'OFF'}")
    console.print()


def main() -> None:
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    backup_self()
    append_log("boot")
    boot()
    bg.start()

    console.print(render_status())
    console.print()
    print_help()
    console.print(Rule(style="dim cyan"))

    greeting = (
        f"Поздоровайся с {CONFIG['owner_name']}. "
        f"Скажи кратко, что ты {APP_NAME}, у тебя безопасные инструменты, sqlite-память и фоновый режим."
    )

    hello = agent.respond(greeting)
    console.print(f"\n[bold bright_green]ARIA ▸[/bold bright_green] [white]{hello}[/white]\n")

    while True:
        pending = bg.pop_pending()
        if pending:
            console.print(f"\n[bold magenta]💭 ФОН ▸[/bold magenta] [dim]{pending}[/dim]\n")

        console.print(Rule(style="dim"))
        user = console.input("[bold blue]ТЫ  ▸[/bold blue] ").strip()

        if not user:
            continue

        low = user.lower()

        if low in {"пока", "exit", "quit", "выкл"}:
            graceful_shutdown()

        elif low == "статус":
            console.print(render_status())
            continue

        elif low == "память":
            command_memory()
            continue

        elif low == "факты":
            command_facts()
            continue

        elif low.startswith("найди "):
            command_search(user[6:].strip())
            continue

        elif low == "заметки":
            command_notes()
            continue

        elif low == "фон":
            command_toggle_bg()
            continue

        elif low == "помощь":
            print_help()
            continue

        else:
            with console.status("[bold cyan]◌ думаю...[/bold cyan]", spinner="dots2"):
                answer = agent.respond(user)

            console.print()
            console.print(render_status())
            console.print(f"\n[bold bright_green]ARIA ▸[/bold bright_green] [white]{answer}[/white]\n")
            append_log(f"USER: {user[:200]}")
            append_log(f"ARIA: {answer[:300]}")


if __name__ == "__main__":
    main()
