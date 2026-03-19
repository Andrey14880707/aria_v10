# main.py
import shutil
import signal
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.text import Text
from rich.align import Align
from rich import box

from agent import Agent
from background import BackgroundWorker
from config import APP_NAME, BACKUP_DIR, CONFIG, MODEL, save_config
from db import MemoryDB
from llm import AnthropicClient
from state import AgentState
from tools import ToolRunner
from utils import append_log

try:
    from selfcheck import SelfCheck
except Exception:
    SelfCheck = None

try:
    from mutation_engine import MutationEngine
except Exception:
    MutationEngine = None

try:
    from evolution import EvolutionManager
except Exception:
    EvolutionManager = None

try:
    from patch_manager import PatchManager
except Exception:
    PatchManager = None


console = Console()
PROJECT_DIR = Path(__file__).resolve().parent
voice_mode: bool = False

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

selfcheck = SelfCheck(PROJECT_DIR) if SelfCheck else None
mutation_engine = MutationEngine(PROJECT_DIR, llm) if MutationEngine else None
evolution_manager = EvolutionManager(PROJECT_DIR, llm) if EvolutionManager else None
patch_manager = PatchManager(PROJECT_DIR) if PatchManager else None


def backup_self() -> None:
    src = Path(__file__).resolve()
    dst = BACKUP_DIR / f"aria_v10_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
    shutil.copy2(src, dst)

    backups = sorted(BACKUP_DIR.glob("aria_v10_*.py"))
    for old in backups[:-20]:
        try:
            old.unlink()
        except Exception:
            pass


def render_status() -> Panel:
    face = FACES.get(state.face, "^_^")
    mood_style = (
        "bold bright_green"
        if state.mood >= 70
        else "bold yellow"
        if state.mood >= 40
        else "bold red"
    )

    face_art = Text()
    face_art.append("╭─────╮\n", style="dim")
    face_art.append(f"│ {face} │\n", style=mood_style)
    face_art.append("╰─────╯", style="dim")

    title = (
        f"[bold cyan]{APP_NAME}[/bold cyan]  "
        f"[dim]session:{state.session_id} "
        f"cmd:{state.commands_run} "
        f"bg:{state.background_cycles} "
        f"sessions:{db.sessions_count()} "
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
        ("голос", "вкл/выкл голосовой режим"),
        ("selfcheck", "проверка системы"),
        ("mutate", "цикл автоэволюции"),
        ("history", "история мутаций"),
        ("rollback [файл]", "откат последнего бэкапа"),
        ("patches", "кандидаты патчей"),
        ("help", "справка"),
    ]

    for row in rows:
        t.add_row(*row)

    console.print(Panel(t, title="[bold]Команды[/bold]", border_style="dim"))


def command_memory() -> None:
    table = Table(box=box.ROUNDED, border_style="cyan", title="Память")
    table.add_column("Параметр", style="dim")
    table.add_column("Значение", style="cyan")
    table.add_row("Сессий", str(db.sessions_count()))
    table.add_row("Фактов", str(db.facts_count()))
    table.add_row("Команд", str(state.commands_run))
    table.add_row("Фоновых циклов", str(state.background_cycles))
    table.add_row("Последняя мысль", state.last_thought[:80])
    console.print(table)


def command_facts() -> None:
    facts = db.search_facts("", limit=15)
    if not facts:
        console.print("[dim]Фактов пока нет.[/dim]")
        return

    text = "\n".join(f"• {f['fact']}" for f in facts)
    console.print(Panel(text, title="Последние факты", border_style="magenta"))


def command_search(query: str) -> None:
    rows = db.search_facts(query, limit=20)
    if not rows:
        console.print(f"[dim]Ничего не найдено по '{query}'.[/dim]")
        return

    text = "\n".join(f"• {r['fact']}" for r in rows)
    console.print(Panel(text, title=f"Найдено: {query}", border_style="cyan"))


def command_notes() -> None:
    rows = db.recent_notes(20)
    if not rows:
        console.print("[dim]Заметок пока нет.[/dim]")
        return

    text = "\n".join(f"[{r['created_at']}] {r['note']}" for r in reversed(rows))
    console.print(Panel(text, title="Заметки", border_style="green"))


def command_toggle_bg() -> None:
    CONFIG["background_enabled"] = not CONFIG["background_enabled"]
    save_config(CONFIG)

    if CONFIG["background_enabled"]:
        bg.start()
        console.print("[green]Фон включен.[/green]")
    else:
        bg.stop()
        console.print("[yellow]Фон выключен.[/yellow]")


def command_toggle_voice() -> None:
    global voice_mode
    voice_mode = not voice_mode
    status = "[green]ВКЛ[/green]" if voice_mode else "[yellow]ВЫКЛ[/yellow]"
    console.print(f"Голосовой режим: {status}")
    if voice_mode:
        console.print("[dim]Ответы ARIA будут озвучены. Введи 'слушай' для голосового ввода.[/dim]")


def command_selfcheck() -> None:
    if not selfcheck:
        console.print("[red]selfcheck недоступен.[/red]")
        return

    try:
        report = selfcheck.health_report()
        table = Table(box=box.ROUNDED, border_style="cyan", title="SelfCheck")
        table.add_column("Проверка", style="dim")
        table.add_column("Статус", style="cyan")

        table.add_row("Общий статус", "OK" if report.get("ok") else "FAIL")

        for name, status in report.get("files", {}).items():
            table.add_row(f"file:{name}", "OK" if status else "FAIL")

        for name, status in report.get("imports", {}).items():
            table.add_row(f"import:{name}", "OK" if status else "FAIL")

        console.print(table)
    except Exception as e:
        console.print(f"[red]Ошибка selfcheck: {e}[/red]")


def command_mutate() -> None:
    if not mutation_engine:
        console.print("[red]mutation_engine недоступен.[/red]")
        return

    try:
        result = mutation_engine.auto_cycle()
        console.print(
            Panel(
                str(result),
                title="Mutation Engine",
                border_style="magenta",
            )
        )
    except Exception as e:
        console.print(f"[red]Ошибка mutate: {e}[/red]")


def command_history() -> None:
    if not mutation_engine:
        console.print("[red]mutation_engine недоступен.[/red]")
        return

    try:
        items = mutation_engine.recent_history(15)
        if not items:
            console.print("[dim]История мутаций пуста.[/dim]")
            return

        lines = []
        for item in items:
            time_value = item.get("time", "?")
            action = item.get("action", "?")
            result = item.get("result", {})
            status = result.get("status", item.get("status", "?")) if isinstance(result, dict) else "?"
            lines.append(f"[{time_value}] {action} -> {status}")

        console.print(Panel("\n".join(lines), title="История мутаций", border_style="cyan"))
    except Exception as e:
        console.print(f"[red]Ошибка history: {e}[/red]")


def command_patches() -> None:
    if not patch_manager:
        console.print("[red]patch_manager недоступен.[/red]")
        return

    try:
        patches = patch_manager.list_patch_candidates()
        if not patches:
            console.print("[dim]Кандидатов патчей нет.[/dim]")
            return

        text = "\n".join(str(p.name) for p in patches[-20:])
        console.print(Panel(text, title="Кандидаты патчей", border_style="magenta"))
    except Exception as e:
        console.print(f"[red]Ошибка patches: {e}[/red]")


def command_rollback(file_name: str) -> None:
    if not patch_manager:
        console.print("[red]patch_manager недоступен.[/red]")
        return

    if not file_name:
        console.print("[yellow]Укажи файл. Пример: rollback agent.py[/yellow]")
        return

    try:
        result = patch_manager.rollback_latest(file_name)
        console.print(Panel(str(result), title="Rollback", border_style="yellow"))
    except Exception as e:
        console.print(f"[red]Ошибка rollback: {e}[/red]")


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
    console.print(f"  [cyan]▸ PROJECT:[/cyan] {PROJECT_DIR}")
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

    try:
        hello = agent.respond(greeting)
    except Exception as e:
        hello = f"Ошибка старта: {e}"

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

        elif low in {"статус", "status"}:
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

        elif low == "голос":
            command_toggle_voice()
            continue

        elif low in {"слушай", "listen"} and voice_mode:
            console.print("[dim]Говори...[/dim]")
            try:
                spoken = tools.execute("listen", {})
                if spoken and spoken != "Голос не распознан.":
                    console.print(f"[bold blue]ТЫ (голос) ▸[/bold blue] {spoken}")
                    user = spoken
                    low = user.lower()
                else:
                    console.print("[yellow]Не удалось распознать голос.[/yellow]")
                    continue
            except Exception as e:
                console.print(f"[red]Ошибка голосового ввода: {e}[/red]")
                continue

        elif low in {"помощь", "help"}:
            print_help()
            continue

        elif low == "selfcheck":
            command_selfcheck()
            continue

        elif low == "mutate":
            command_mutate()
            continue

        elif low == "history":
            command_history()
            continue

        elif low == "patches":
            command_patches()
            continue

        elif low.startswith("rollback "):
            command_rollback(user.split(" ", 1)[1].strip())
            continue

        else:
            try:
                with console.status("[bold cyan]◌ думаю...[/bold cyan]", spinner="dots2"):
                    answer = agent.respond(user)

                console.print()
                console.print(render_status())
                console.print(f"\n[bold bright_green]ARIA ▸[/bold bright_green] [white]{answer}[/white]\n")
                append_log(f"USER: {user[:200]}")
                append_log(f"ARIA: {answer[:300]}")

                if voice_mode:
                    try:
                        tools.execute("speak", {"text": answer[:500]})
                    except Exception:
                        pass
            except Exception as e:
                append_log(f"ERROR: {e}")
                if selfcheck:
                    try:
                        selfcheck.log_error(e, "main_loop")
                    except Exception:
                        pass
                console.print(f"[red]Ошибка: {e}[/red]")


if __name__ == "__main__":
    main()
