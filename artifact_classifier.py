"""ArtifactClassifier — infers Space type and best template from a user prompt."""

import re
from typing import Optional

# keyword → (type, template)
_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"(морск|battleship|корабл|sea\s*battle|naval)", re.I),
     "web_app", "game_battleship"),
    (re.compile(r"(игр[аеу]|game|pygame|тетрис|tetris|змей|snake|арканоид)", re.I),
     "web_app", "game_battleship"),
    (re.compile(r"(калькулятор|calculator|вычисл)", re.I),
     "web_app", "calculator_basic"),
    (re.compile(r"(дашборд|dashboard|панел[ьи]|статистик|chart|график)", re.I),
     "web_app", "dashboard_basic"),
    (re.compile(r"(landing|лэндинг|одностраниц|сайт|страниц)", re.I),
     "web_app", "landing_page"),
    (re.compile(r"(fastapi|flask|django|rest\s*api|сервер|backend)", re.I),
     "code_tool", "fastapi_basic"),
    (re.compile(r"(cli|скрипт|script|python|утилит)", re.I),
     "code_tool", "python_cli"),
    (re.compile(r"(поток|workflow|автоматиз|flow|pipeline)", re.I),
     "workflow", "basic_flow"),
]

_DEFAULT_WEB = ("web_app", "landing_page")


def classify(prompt: str) -> tuple[str, str]:
    """Return (space_type, template_id) for a prompt."""
    for pattern, stype, template in _RULES:
        if pattern.search(prompt):
            return stype, template
    return _DEFAULT_WEB
