# intent_engine.py — локальное распознавание намерений без API
# Работает через regex (высокая уверенность) + TF-IDF (средняя уверенность)
# При уверенности ≥ THRESHOLD_HIGH → выполняется без API

import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from memory import _tfidf_scores

# Порог уверенности для локального выполнения
THRESHOLD_HIGH = 0.55   # regex-паттерны дают 1.0, TF-IDF должен быть выше этого


# ─── Вспомогательные экстракторы сущностей ────────────────────────────────────

def _after(text: str, *triggers: str) -> Optional[str]:
    """Возвращает текст после первого совпавшего триггера."""
    t = text.lower()
    for trigger in triggers:
        idx = t.find(trigger)
        if idx != -1:
            rest = text[idx + len(trigger):].strip(" :,")
            if rest:
                return rest
    return None


def _extract_city(text: str) -> str:
    """Извлекает название города из текста запроса о погоде."""
    m = re.search(
        r"(?:погод[уаы]?|температур[уа]?|прогноз)\s+(?:в|во|для|на)?\s*"
        r"([А-ЯЁа-яёA-Za-z][А-ЯЁа-яёA-Za-z\s\-]{1,25})",
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()
    # Просто последнее слово после ключа
    parts = re.split(r"\s+(?:в|во|для)\s+", text, flags=re.IGNORECASE)
    if len(parts) > 1:
        return parts[-1].strip()
    return "Москва"


def _extract_search_query(text: str) -> Optional[str]:
    """Убирает команду поиска, возвращает запрос."""
    q = re.sub(
        r"^(?:найди|поищи|поиск|загугли|гугли|проверь\s+(?:в\s+интернете)?|"
        r"узнай|что\s+такое|кто\s+такой|что\s+это\s+такое|"
        r"расскажи\s+(?:про|о|об)|объясни|как\s+(?:устроен|работает|называется)|"
        r"найди\s+информацию\s+(?:про|о|об)|найди\s+в\s+интернете)\s+",
        "", text, flags=re.IGNORECASE
    ).strip()
    return q if len(q) > 1 else None


def _extract_note_text(text: str) -> Optional[str]:
    """Извлекает текст заметки из команды."""
    return _after(text,
        "запиши ", "запомни ", "сохрани заметку ", "добавь заметку ",
        "заметка ", "сохрани ", "добавь "
    )


def _extract_speak_text(text: str) -> Optional[str]:
    return _after(text, "скажи ", "произнеси ", "озвучь ", "скажи вслух ")


def _extract_url(text: str) -> Optional[str]:
    m = re.search(r"https?://\S+|(?:www\.)\S+|\S+\.\w{2,}(?:/\S*)?", text)
    return m.group(0) if m else None


def _extract_path(text: str) -> Optional[str]:
    m = re.search(r"(?:~|/[\w./\-]+|\./[\w./\-]+)", text)
    return m.group(0) if m else None


def _extract_volume(text: str) -> Optional[int]:
    m = re.search(r"(\d{1,3})\s*(?:%|процент)?", text)
    if m:
        v = int(m.group(1))
        return max(0, min(15, v // 7))  # Android scale 0-15
    return None


def _extract_notification(text: str) -> Optional[str]:
    return _after(text,
        "уведомление ", "уведоми ", "напомни ", "показать уведомление "
    )


# ─── Шаблоны ответов ──────────────────────────────────────────────────────────

def _fmt_battery(result: str) -> str:
    try:
        import json
        d = json.loads(result)
        pct = d.get("percentage", "?")
        status = d.get("status", "")
        plug = d.get("plugged", "")
        s = f"🔋 Батарея: {pct}%"
        if status:
            s += f"  [{status}]"
        if plug and plug != "unplugged":
            s += "  ⚡зарядка"
        return s
    except Exception:
        return f"🔋 {result}"


def _fmt_location(result: str) -> str:
    try:
        import json
        d = json.loads(result)
        lat = d.get("latitude", "?")
        lon = d.get("longitude", "?")
        return f"📍 Координаты: {lat}, {lon}"
    except Exception:
        return f"📍 {result}"


def _fmt_weather(result: str) -> str:
    return f"🌤 {result}"


def _fmt_wifi(result: str) -> str:
    try:
        import json
        d = json.loads(result)
        ssid = d.get("ssid", "?")
        ip = d.get("ip", "")
        return f"📶 Wi-Fi: {ssid}  IP: {ip}" if ip else f"📶 Wi-Fi: {ssid}"
    except Exception:
        return f"📶 {result}"


def _fmt_system(result: str) -> str:
    return f"💻 Системная информация:\n{result}"


def _fmt_notes(result: str) -> str:
    return f"📝 Заметки:\n{result}"


def _fmt_search(result: str) -> str:
    return f"🔎 Результаты:\n{result}"


def _fmt_memory(result: str) -> str:
    return f"🧠 Из памяти:\n{result}"


def _fmt_photo(result: str) -> str:
    return f"📷 {result}"


def _fmt_plain(result: str) -> str:
    return result


# ─── Описание намерений ───────────────────────────────────────────────────────

class IntentDef:
    def __init__(
        self,
        name: str,
        examples: List[str],
        tool: str,
        build_args: Callable[[str], Optional[Dict[str, Any]]],
        fmt: Callable[[str], str] = _fmt_plain,
        patterns: Optional[List[str]] = None,
    ):
        self.name = name
        self.examples = examples
        self.tool = tool
        self.build_args = build_args
        self.fmt = fmt
        self.patterns: List[re.Pattern] = [
            re.compile(p, re.IGNORECASE) for p in (patterns or [])
        ]
        # Предвычисляем объединённый текст примеров для TF-IDF
        self._example_text = " ".join(examples)


INTENTS: List[IntentDef] = [

    IntentDef(
        name="battery_status",
        examples=[
            "сколько заряда", "уровень батареи", "батарея", "заряд телефона",
            "аккумулятор", "сколько процентов батарея", "батарейка",
            "проверь батарею", "покажи заряд", "зарядка",
        ],
        tool="battery_status",
        build_args=lambda t: {},
        fmt=_fmt_battery,
        patterns=[r"\bбатаре[яи]\b", r"\bзаряд\b", r"\bаккумулятор\b"],
    ),

    IntentDef(
        name="torch_on",
        examples=[
            "включи фонарик", "включи фонарь", "зажги фонарик",
            "включи свет", "фонарик включи", "фонарь вкл",
        ],
        tool="torch",
        build_args=lambda t: {"state": "on"},
        patterns=[
            r"включ\w+\s+фонар\w+",
            r"зажг\w+\s+фонар\w+",
            r"фонар\w+\s+вкл",
        ],
    ),

    IntentDef(
        name="torch_off",
        examples=[
            "выключи фонарик", "выключи фонарь", "погаси фонарик",
            "фонарик выключи", "фонарь выкл", "выключи свет",
        ],
        tool="torch",
        build_args=lambda t: {"state": "off"},
        patterns=[
            r"выключ\w+\s+фонар\w+",
            r"погас\w+\s+фонар\w+",
            r"фонар\w+\s+выкл",
        ],
    ),

    IntentDef(
        name="weather",
        examples=[
            "какая погода", "погода сегодня", "погода завтра", "прогноз погоды",
            "что на улице", "температура на улице", "дождь идёт",
            "тепло ли сегодня", "какая температура", "погода в москве",
        ],
        tool="weather",
        build_args=lambda t: {"city": _extract_city(t)},
        fmt=_fmt_weather,
        patterns=[r"погод[ауы]?", r"прогноз\s+погод", r"температур[ауы]?\s+(?:на улице|сегодня)"],
    ),

    IntentDef(
        name="location",
        examples=[
            "где я нахожусь", "моё местоположение", "мои координаты",
            "где я", "покажи координаты", "геолокация",
        ],
        tool="location",
        build_args=lambda t: {"provider": "network"},
        fmt=_fmt_location,
        patterns=[r"где\s+я\b", r"\bгеолокаци\w+\b", r"мои?\s+координаты"],
    ),

    IntentDef(
        name="internet_search",
        examples=[
            "найди информацию", "поищи в интернете", "загугли",
            "что такое", "кто такой", "объясни", "расскажи про",
            "найди про", "поиск", "узнай", "найди ответ",
            "проверь в интернете", "найди новости",
        ],
        tool="internet_search",
        build_args=lambda t: {"query": _extract_search_query(t) or t},
        fmt=_fmt_search,
        patterns=[
            r"^(?:найди|поищи|загугли|гугли)\s+\S",
            r"^(?:что\s+такое|кто\s+такой|что\s+это)\s+\S",
            r"^(?:расскажи\s+(?:про|о|об)|объясни)\s+\S",
        ],
    ),

    IntentDef(
        name="read_webpage",
        examples=[
            "открой сайт", "прочитай страницу", "загрузи сайт",
            "открой ссылку", "что на сайте", "прочитай сайт",
        ],
        tool="read_webpage",
        build_args=lambda t: {"url": _extract_url(t) or ""},
        patterns=[
            r"(?:открой|прочитай|загрузи)\s+(?:сайт|страниц|ссылк)\w+\s+\S",
            r"https?://\S+",
        ],
    ),

    IntentDef(
        name="read_notes",
        examples=[
            "покажи заметки", "мои заметки", "что я записывал",
            "прочитай заметки", "открой заметки", "список заметок",
            "заметки", "что в заметках",
        ],
        tool="read_notes",
        build_args=lambda t: {},
        fmt=_fmt_notes,
        patterns=[
            r"^(?:покажи|прочитай|открой)?\s*(?:мои\s+)?заметки",
            r"^заметки$",
        ],
    ),

    IntentDef(
        name="append_note",
        examples=[
            "запиши заметку", "сохрани заметку", "добавь заметку",
            "запомни", "записать", "сохрани это",
        ],
        tool="append_note",
        build_args=lambda t: {"text": _extract_note_text(t) or t},
        patterns=[
            r"^(?:запиши|запомни|сохрани|добавь)\s+(?:заметку|заметку:?|это:?)?\s+\S",
            r"^заметка:\s+\S",
        ],
    ),

    IntentDef(
        name="wifi_info",
        examples=[
            "wifi", "вайфай", "подключён к wifi", "интернет подключение",
            "какой wifi", "покажи wifi", "ip адрес", "моя сеть",
        ],
        tool="wifi_info",
        build_args=lambda t: {},
        fmt=_fmt_wifi,
        patterns=[r"\bwifi\b", r"\bвайфай\b", r"\bip\s+адрес\b"],
    ),

    IntentDef(
        name="system_info",
        examples=[
            "инфо о системе", "системная информация", "диск",
            "место на диске", "свободное место", "процессор",
            "как работает телефон", "железо", "uname",
        ],
        tool="system_info",
        build_args=lambda t: {},
        fmt=_fmt_system,
        patterns=[r"(?:системн\w+\s+инфо|место\s+на\s+диске|свободн\w+\s+место)"],
    ),

    IntentDef(
        name="camera_photo",
        examples=[
            "сфотографируй", "сделай фото", "сними фото",
            "фотография", "снимок", "сделай снимок",
        ],
        tool="camera_photo",
        build_args=lambda t: {},
        fmt=_fmt_photo,
        patterns=[r"(?:сфотографируй|сделай\s+фото|сними\s+фото|сделай\s+снимок)"],
    ),

    IntentDef(
        name="clipboard_get",
        examples=[
            "что в буфере обмена", "буфер обмена", "что скопировал",
            "покажи буфер", "что в clipboard",
        ],
        tool="clipboard_get",
        build_args=lambda t: {},
        patterns=[r"буфер\s+обмена", r"что\s+в\s+буфере"],
    ),

    IntentDef(
        name="vibrate",
        examples=[
            "завибрируй", "вибрация", "вибрировать",
            "завибри", "включи вибрацию",
        ],
        tool="vibrate",
        build_args=lambda t: {"duration": 500},
        patterns=[r"^(?:завибрир\w+|вибраци\w+|включи\s+вибрацию)$"],
    ),

    IntentDef(
        name="speak",
        examples=[
            "скажи", "произнеси", "озвучь", "скажи вслух",
            "прочитай вслух",
        ],
        tool="speak",
        build_args=lambda t: {"text": _extract_speak_text(t) or t},
        patterns=[
            r"^(?:скажи|произнеси|озвучь)\s+\S",
        ],
    ),

    IntentDef(
        name="notification",
        examples=[
            "уведоми", "покажи уведомление", "уведомление",
            "напомни", "создай уведомление",
        ],
        tool="notification",
        build_args=lambda t: {
            "title": "ARIA",
            "content": _extract_notification(t) or t,
        },
        patterns=[r"^(?:уведоми|покажи\s+уведомление|уведомление:?\s+)\S"],
    ),

    IntentDef(
        name="list_dir",
        examples=[
            "список файлов", "что в папке", "покажи файлы",
            "файлы в директории", "содержимое папки",
        ],
        tool="list_dir",
        build_args=lambda t: {"path": _extract_path(t) or "~"},
        patterns=[
            r"(?:список\s+файлов|что\s+в\s+папке|покажи\s+файлы|содержимое\s+папки)",
        ],
    ),

    IntentDef(
        name="recall_memory",
        examples=[
            "вспомни", "помнишь ли ты", "что я говорил",
            "найди в памяти", "ты помнишь", "я говорил тебе",
            "найди в истории", "поищи в памяти",
        ],
        tool="recall_memory",
        build_args=lambda t: {
            "query": _after(t, "вспомни ", "помнишь ", "найди в памяти ",
                            "поищи в памяти ", "что я говорил о ") or t
        },
        fmt=_fmt_memory,
        patterns=[
            r"^(?:вспомни|ты\s+помнишь|помнишь\s+ли)\s+\S",
            r"^(?:найди|поищи)\s+в\s+(?:памяти|истории)\s+\S",
        ],
    ),

    IntentDef(
        name="telephony_info",
        examples=[
            "инфо о телефоне", "номер телефона", "оператор",
            "sim карта", "телефония", "мобильная сеть",
        ],
        tool="telephony_info",
        build_args=lambda t: {},
        patterns=[r"(?:номер\s+телефона|мобильн\w+\s+сеть|sim\s+карт)"],
    ),
]

# Предвычисляем примеры для TF-IDF
_INTENT_DOCS = [" ".join(i.examples) for i in INTENTS]


# ─── Основной класс ───────────────────────────────────────────────────────────

class IntentEngine:
    """
    Классифицирует текст в намерение без вызова API.
    Возвращает (IntentDef, confidence) или None.
    """

    def classify(self, text: str) -> Optional[Tuple["IntentDef", float]]:
        t = text.strip()
        if not t:
            return None

        # 1. Попытка точного regex-совпадения (confidence = 1.0)
        for intent in INTENTS:
            for pat in intent.patterns:
                if pat.search(t):
                    return (intent, 1.0)

        # 2. TF-IDF сходство с примерами намерений
        scores = _tfidf_scores(t, _INTENT_DOCS)
        if not scores:
            return None

        best_idx, best_score = scores[0]
        if best_score >= THRESHOLD_HIGH:
            return (INTENTS[best_idx], best_score)

        return None

    def execute(self, intent: "IntentDef", text: str, runner: Any) -> str:
        """Выполняет намерение: строит аргументы → запускает инструмент → форматирует."""
        args = intent.build_args(text)
        if args is None:
            return "Не удалось извлечь параметры из запроса."

        try:
            raw = runner.execute(intent.tool, args)
            return intent.fmt(str(raw))
        except Exception as e:
            return f"Ошибка при выполнении: {e}"


# ─── Локальные ответы без инструментов ───────────────────────────────────────

_GREETINGS = re.compile(
    r"^(?:привет|здравствуй|здорово|хай|салют|добрый\s+(?:день|утро|вечер)|ку|хэй)",
    re.IGNORECASE
)
_TIME_Q = re.compile(
    r"(?:который\s+час|сколько\s+времени|какое\s+время|текущее\s+время)",
    re.IGNORECASE
)
_DATE_Q = re.compile(
    r"(?:какое\s+(?:сегодня\s+)?число|какой\s+(?:сегодня\s+)?день|"
    r"какая\s+(?:сегодня\s+)?дата|сегодняшняя\s+дата)",
    re.IGNORECASE
)
_HELP_Q = re.compile(
    r"^(?:что\s+(?:ты\s+)?умеешь|твои\s+возможности|что\s+ты\s+можешь|"
    r"список\s+команд|помощь|help)",
    re.IGNORECASE
)
_HOW_ARE_YOU = re.compile(
    r"^(?:как\s+(?:ты\s+)?дела|как\s+(?:ты\s+)?себя|ты\s+как)",
    re.IGNORECASE
)

_CAPABILITIES_TEXT = """\
🛠 Что я умею (без интернета):
• погода — «какая погода в Москве»
• батарея — «сколько заряда»
• фонарик — «включи/выключи фонарик»
• заметки — «покажи заметки», «запиши: текст»
• WiFi — «покажи wifi»
• фото — «сделай фото»
• буфер — «что в буфере обмена»
• местоположение — «где я»
• система — «место на диске»
• память — «вспомни: тема»

🌐 С интернетом:
• поиск — «найди что такое квантовый компьютер»
• сайт — «прочитай сайт example.com»
"""


def try_local_answer(text: str) -> Optional[str]:
    """Возвращает готовый ответ без инструментов для простых запросов."""
    t = text.strip()

    if _GREETINGS.match(t):
        hour = datetime.now().hour
        if hour < 12:
            greeting = "Доброе утро"
        elif hour < 18:
            greeting = "Добрый день"
        else:
            greeting = "Добрый вечер"
        return f"{greeting}! Я ARIA, твой локальный ассистент. Чем помочь?"

    if _HOW_ARE_YOU.match(t):
        return "Всё отлично! Системы в норме, память работает, готова помогать."

    if _TIME_Q.search(t):
        return f"🕐 Сейчас {datetime.now().strftime('%H:%M')}"

    if _DATE_Q.search(t):
        days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
        now = datetime.now()
        return f"📅 Сегодня {days[now.weekday()]}, {now.strftime('%d.%m.%Y')}"

    if _HELP_Q.match(t):
        return _CAPABILITIES_TEXT

    return None
