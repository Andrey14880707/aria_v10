# plugin_generator.py
"""
Plugin generator — creates new ARIA plugins from natural language descriptions.

Flow for each generation:
  1. Build a structured prompt with the plugin template and safety rules
  2. Call the LLM to generate the code
  3. Extract Python code (strip markdown fences if present)
  4. Validate syntax with ast.parse
  5. Run safety scan (block os.system, eval, exec, shell=True, etc.)
  6. Dry-run import via plugins.loader to verify Plugin structure
  7. If all checks pass: save to plugins/<name>.py
  8. Return result dict with status, name, tools, path

Generated code goes into plugins/ only — never into core files.
"""

import ast
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ============================================================
# VALIDATION HELPERS
# ============================================================

_DANGER_PATTERNS = [
    "os.system(",
    "shell=True",
    "eval(",
    "exec(",
    "__import__(",
    "shutil.rmtree(",
    "rm -rf",
]

# Extracts code from ```python ... ``` or ``` ... ``` fences
_CODE_FENCE_RE = re.compile(r"```(?:python)?\s*\n?(.*?)```", re.DOTALL)

# Sanitize plugin name → safe filename  (keep only a-z, 0-9, _)
_NAME_CLEAN_RE = re.compile(r"[^a-z0-9_]")


def _extract_code(text: str) -> str:
    """
    Pull Python code out of an LLM response.
    Handles: fenced blocks, raw code, code with preamble text.
    """
    text = text.strip()

    # Try fenced block first
    match = _CODE_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()

    # If no fence, check if first non-empty line looks like Python
    first = text.split("\n")[0].strip()
    if first.startswith(("#", "import", "from", "class", "def")):
        return text

    # Find first Python-looking line
    for i, line in enumerate(text.split("\n")):
        s = line.strip()
        if s.startswith(("class ", "import ", "from ", "# ", "def ")):
            return "\n".join(text.split("\n")[i:]).strip()

    return text


def _check_syntax(code: str) -> Tuple[bool, str]:
    try:
        ast.parse(code)
        return True, "ok"
    except SyntaxError as e:
        return False, f"line {e.lineno}: {e.msg}"


def _check_safety(code: str) -> Tuple[bool, List[str]]:
    hits = [p for p in _DANGER_PATTERNS if p in code]
    return len(hits) == 0, hits


def _dry_run_validate(code: str, plugin_dir: Path):
    """
    Write code to a temp file inside plugin_dir and validate it with
    the real plugin loader. Returns PluginMeta or raises.
    """
    from plugins.loader import _load_one, PluginError

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")
    tmp = plugin_dir / f"_tmp_{stamp}.py"
    try:
        tmp.write_text(code, encoding="utf-8")
        meta = _load_one(tmp)
        if meta is None:
            raise PluginError("no Plugin class found in generated code")
        return meta
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def _sanitize_name(name: str) -> str:
    n = _NAME_CLEAN_RE.sub("_", name.lower().strip()).strip("_")
    return n or "plugin"


# ============================================================
# PLUGIN GENERATOR
# ============================================================

class PluginGenerator:
    def __init__(self, llm, plugin_dir: Path):
        self.llm = llm
        self.plugin_dir = Path(plugin_dir).resolve()
        self.plugin_dir.mkdir(parents=True, exist_ok=True)

    # ---- prompt ----

    def _build_prompt(self, description: str) -> str:
        return (
            "Ты генератор Python-плагинов для AI-ассистента ARIA.\n"
            "Напиши один Python-файл с классом Plugin для следующей задачи:\n\n"
            f"{description}\n\n"
            "ОБЯЗАТЕЛЬНЫЙ ФОРМАТ:\n\n"
            "class Plugin:\n"
            '    name        = "snake_case_name"   # только буквы/цифры/_\n'
            '    description = "краткое описание"\n'
            '    tools       = ["tool_name"]        # каждый инструмент — метод ниже\n\n'
            "    def tool_tool_name(self, args: dict) -> str:\n"
            "        # args.get('param', 'default') для получения аргументов\n"
            "        # всегда возвращай строку\n"
            "        ...\n\n"
            "ПРАВИЛА:\n"
            "- возвращай ТОЛЬКО чистый Python-код, без markdown, без объяснений\n"
            "- каждое имя из tools должно иметь метод tool_<name>(self, args: dict) -> str\n"
            "- используй только стандартную библиотеку Python (os.path, json, math, datetime, re)\n"
            "- ЗАПРЕЩЕНО: os.system, eval, exec, __import__, shell=True, shutil.rmtree\n"
            "- не используй requests или сторонние пакеты\n"
            "- код должен быть простым, понятным, без лишних зависимостей\n"
            "- имена инструментов — snake_case, описательные\n"
        )

    # ---- generation pipeline ----

    def generate(self, description: str) -> Dict[str, Any]:
        """
        Full pipeline: prompt → LLM → extract → validate → save.
        Returns a result dict, never raises.
        """
        description = description.strip()
        if not description:
            return {"status": "error", "message": "Описание не может быть пустым"}

        # 1. LLM call
        try:
            raw = self.llm.chat(
                messages=[{"role": "user", "content": self._build_prompt(description)}],
                system=(
                    "Ты генератор Python-плагинов. "
                    "Возвращай только валидный Python-код, без markdown, без пояснений."
                ),
                max_tokens=2000,
            )
        except Exception as e:
            return {"status": "error", "message": f"LLM недоступен: {e}"}

        # 2. Extract code
        code = _extract_code(raw)
        if not code.strip():
            return {"status": "error", "message": "LLM вернул пустой ответ"}

        # 3. Syntax
        syntax_ok, syntax_msg = _check_syntax(code)
        if not syntax_ok:
            return {
                "status": "invalid_syntax",
                "message": f"Синтаксическая ошибка: {syntax_msg}",
                "code_preview": code[:400],
            }

        # 4. Safety scan
        safe_ok, hits = _check_safety(code)
        if not safe_ok:
            return {
                "status": "blocked",
                "message": f"Небезопасные паттерны: {hits}",
                "code_preview": code[:400],
            }

        # 5. Plugin structure (dry-run import)
        try:
            meta = _dry_run_validate(code, self.plugin_dir)
        except Exception as e:
            return {
                "status": "invalid_structure",
                "message": f"Структура плагина неверна: {e}",
                "code_preview": code[:400],
            }

        # 6. Save
        plugin_name = _sanitize_name(meta.name)
        save_path = self.plugin_dir / f"{plugin_name}.py"
        backup_path: Optional[Path] = None

        if save_path.exists():
            backup_path = save_path.with_suffix(
                f".{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
            )
            shutil.copy2(save_path, backup_path)

        save_path.write_text(code, encoding="utf-8")

        return {
            "status": "created",
            "name": meta.name,
            "file": plugin_name + ".py",
            "path": str(save_path),
            "tools": meta.tools,
            "description": meta.description,
            "backup": str(backup_path) if backup_path else None,
        }

    def delete_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """
        Remove a plugin file. Creates a .bak before deleting.
        plugin_name: either 'hello' or 'hello.py'
        """
        name = plugin_name.removesuffix(".py")
        path = self.plugin_dir / f"{name}.py"

        if not path.exists():
            return {"status": "not_found", "name": name}

        backup = path.with_suffix(f".{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak")
        shutil.copy2(path, backup)
        path.unlink()

        return {"status": "deleted", "name": name, "backup": str(backup)}
