# offline.py
"""
Local command handler — answers without calling any LLM.

Use for: calculator, date/time, ping, basic info.
Keeps ARIA useful when the API is down or the user just wants a quick answer.

Usage:
    offline = OfflineHandler()
    result = offline.handle(user_text)   # returns str or None
    if result is None:
        # forward to LLM
    ...
    except LLMError as e:
        answer = offline.handle_fallback(user_text, str(e))
"""

import ast
import math
import operator
import re
from datetime import datetime
from typing import Optional


# ============================================================
# SAFE CALCULATOR — no eval(), pure AST walk
# ============================================================

_OPS = {
    ast.Add:      operator.add,
    ast.Sub:      operator.sub,
    ast.Mult:     operator.mul,
    ast.Div:      operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod:      operator.mod,
    ast.Pow:      operator.pow,
    ast.USub:     operator.neg,
    ast.UAdd:     operator.pos,
}

_NAMES = {
    "pi":  math.pi,
    "e":   math.e,
    "tau": math.tau,
    "inf": math.inf,
}

_FUNCS = {
    "sqrt":      math.sqrt,
    "abs":       abs,
    "round":     round,
    "int":       int,
    "float":     float,
    "sin":       math.sin,
    "cos":       math.cos,
    "tan":       math.tan,
    "asin":      math.asin,
    "acos":      math.acos,
    "atan":      math.atan,
    "log":       math.log,
    "log2":      math.log2,
    "log10":     math.log10,
    "ceil":      math.ceil,
    "floor":     math.floor,
    "factorial": math.factorial,
}

# Looks like a pure math expression: digits, spaces, basic operators, parens, dot
_MATH_RE = re.compile(r"^[\d\s\+\-\*\/\.\(\)\^%,]+$")


def _eval_node(node):
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)):
            raise ValueError(f"unsupported constant: {type(node.value).__name__}")
        return node.value

    if isinstance(node, ast.BinOp):
        fn = _OPS.get(type(node.op))
        if fn is None:
            raise ValueError(f"unsupported operator: {type(node.op).__name__}")
        return fn(_eval_node(node.left), _eval_node(node.right))

    if isinstance(node, ast.UnaryOp):
        fn = _OPS.get(type(node.op))
        if fn is None:
            raise ValueError(f"unsupported unary op: {type(node.op).__name__}")
        return fn(_eval_node(node.operand))

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("only simple function calls are allowed")
        fn = _FUNCS.get(node.func.id)
        if fn is None:
            raise ValueError(f"unknown function: {node.func.id}")
        args = [_eval_node(a) for a in node.args]
        return fn(*args)

    if isinstance(node, ast.Name):
        if node.id in _NAMES:
            return _NAMES[node.id]
        if node.id in _FUNCS:
            raise ValueError(f"{node.id} нужны скобки: {node.id}(...)")
        raise ValueError(f"unknown name: {node.id}")

    raise ValueError(f"unsupported expression: {type(node).__name__}")


def safe_calc(expr: str) -> str:
    """
    Evaluate a math expression safely.
    Supports: +−*/**, (), sqrt, sin, cos, log, factorial, pi, e, etc.
    Returns result as string, or an error message.
    """
    expr = expr.strip().replace("^", "**").replace(",", ".")
    if not expr:
        return "укажи выражение"
    try:
        tree = ast.parse(expr, mode="eval")
        result = _eval_node(tree.body)
        if isinstance(result, float):
            if result.is_integer() and abs(result) < 1e15:
                return str(int(result))
            return f"{result:.10g}"
        return str(result)
    except ZeroDivisionError:
        return "ошибка: деление на ноль"
    except (ValueError, TypeError) as e:
        return f"ошибка: {e}"
    except Exception:
        return "не могу вычислить"


# ============================================================
# DATE / TIME HELPERS
# ============================================================

_WEEKDAYS = [
    "Понедельник", "Вторник", "Среда", "Четверг",
    "Пятница", "Суббота", "Воскресенье",
]

_MONTHS = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def _nice_date(now: Optional[datetime] = None) -> str:
    now = now or datetime.now()
    return f"{_WEEKDAYS[now.weekday()]}, {now.day} {_MONTHS[now.month]} {now.year}"


# ============================================================
# OFFLINE HANDLER
# ============================================================

class OfflineHandler:
    """
    Try to answer common user requests locally — instant, no network.

    integrate in main loop:
        result = offline.handle(user_text)
        if result is not None:
            show result, continue
        else:
            send to LLM, use handle_fallback() on error
    """

    def handle(self, text: str) -> Optional[str]:
        """
        Return a local response string, or None if LLM should handle it.
        """
        s = text.strip()
        low = s.lower()

        # ---- calculator: explicit prefix ----
        for prefix in ("calc ", "calculate ", "считай ", "вычисли ", "= "):
            if low.startswith(prefix):
                expr = s[len(prefix):].strip()
                return f"= {safe_calc(expr)}" if expr else "укажи выражение: calc 2+2"

        # ---- calculator: looks like bare math (2+2, 3*7, sqrt(9)) ----
        if _MATH_RE.match(low) and any(c.isdigit() for c in low):
            return f"= {safe_calc(s)}"

        # ---- time ----
        if low in {"время", "time", "который час", "сколько времени", "hh:mm"}:
            return datetime.now().strftime("%H:%M:%S")

        # ---- date ----
        if low in {"дата", "date", "какое число", "сегодня", "today"}:
            return _nice_date()

        # ---- weekday ----
        if low in {"день", "день недели", "weekday"}:
            return _WEEKDAYS[datetime.now().weekday()]

        # ---- date + time ----
        if low in {"now", "сейчас", "дата и время", "datetime"}:
            now = datetime.now()
            return f"{_nice_date(now)}  {now.strftime('%H:%M:%S')}"

        # ---- ping / liveness check ----
        if low in {"пинг", "ping", "тест", "test", "живой?", "жива?"}:
            return "pong — ARIA онлайн"

        return None  # forward to LLM

    def handle_fallback(self, user_text: str, error: str) -> str:
        """
        Called when the LLM raises an error.
        Tries offline first; if nothing matches, returns a graceful degraded message.
        """
        result = self.handle(user_text)
        if result is not None:
            return result
        short = str(error)[:120]
        return (
            f"[офлайн] API недоступен: {short}\n"
            "Без сети работают: calc, время, дата, день, пинг"
        )

    @staticmethod
    def help_text() -> str:
        return (
            "Локальные команды (работают без сети / мгновенно):\n"
            "  calc <выражение>  вычислить: calc 2+2, calc sqrt(9), calc pi*2\n"
            "  время / time      текущее время\n"
            "  дата / date       сегодняшняя дата\n"
            "  день              день недели\n"
            "  сейчас / now      дата + время\n"
            "  пинг / ping       проверить работу ARIA"
        )
