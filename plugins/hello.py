# plugins/hello.py
"""
Example plugin — shows how to write an ARIA plugin.

Drop any .py file with a Plugin class into aria_v10/plugins/
and it will be auto-loaded at startup.
"""

from datetime import datetime


class Plugin:
    name        = "hello"
    description = "Greeting example — says hello and shows current time"
    tools       = ["greet", "uptime_info"]

    def tool_greet(self, args: dict) -> str:
        """Say hello to someone. Args: {"name": "Андрей"}"""
        name = str(args.get("name", "мир")).strip() or "мир"
        hour = datetime.now().hour
        if hour < 6:
            greeting = "Доброй ночи"
        elif hour < 12:
            greeting = "Доброе утро"
        elif hour < 18:
            greeting = "Добрый день"
        else:
            greeting = "Добрый вечер"
        return f"{greeting}, {name}! Это ответ из плагина hello."

    def tool_uptime_info(self, args: dict) -> str:
        """Return current timestamp. Args: {}"""
        return f"Plugin hello работает. Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
