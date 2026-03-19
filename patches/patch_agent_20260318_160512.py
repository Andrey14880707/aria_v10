import json
from typing import Dict, Any, List

from db import MemoryDB
from llm import AnthropicClient
from state import AgentState
from tools import ToolRunner


class Agent:
    def __init__(
        self,
        llm: AnthropicClient,
        db: MemoryDB,
        state: AgentState,
        tools: ToolRunner,
    ):
        self.llm = llm
        self.db = db
        self.state = state
        self.tools = tools

    def _system_prompt(self) -> str:
        base = """
Ты ARIA — локальный AI ассистент в Termux/Android.

Правила:
- отвечай кратко и по делу
- если нужен инструмент, вызывай его JSON-объектом
- не пиши объяснения ДО вызова инструмента
- если пользователь просит открыть/включить/запустить приложение, ОБЯЗАТЕЛЬНО используй tool open_app
- если пользователь просит нажать, свайпнуть, ввести текст, открыть URL, сделать скриншот, использовать буфер обмена или системные функции — используй подходящий инструмент
- не говори "не могу", пока не попытался вызвать инструмент
- после результата инструмента дай обычный человеческий ответ

Формат вызова инструмента:
{
  "type": "tool_call",
  "tool": "open_app",
  "args": {
    "name": "instagram"
  }
}

Доступные инструменты:
- battery_status
- location
- camera_photo
- speak
- notification
- torch
- weather
- internet_search
- read_notes
- append_note
- system_info
- list_dir
- read_file
- list_packages
- open_app
- open_url
- tap
- swipe
- input_text
- keyevent
- screenshot
- get_screen_size
- get_current_app
- open_settings
- clipboard_get
- clipboard_set
- share
- vibrate
- volume
- wifi_info
- telephony_info
- download_file
- http_get
- run_termux_intent
- sleep
- echo

Примеры:
Пользователь: открой instagram
Ответ:
{"type":"tool_call","tool":"open_app","args":{"name":"instagram"}}

Пользователь: открой телеграм
Ответ:
{"type":"tool_call","tool":"open_app","args":{"name":"telegram"}}

Пользователь: открой сайт openai.com
Ответ:
{"type":"tool_call","tool":"open_url","args":{"url":"openai.com"}}

Пользователь: сделай скриншот
Ответ:
{"type":"tool_call","tool":"screenshot","args":{}}
""".strip()

        # Append plugin tools so the model knows about them
        plugin_tools = self.tools.get_plugin_tool_names()
        if plugin_tools:
            base += "\n\nИнструменты плагинов:\n" + "\n".join(
                f"- {t}" for t in plugin_tools
            )

        return base

    def _build_messages(self, user_text: str) -> List[Dict[str, str]]:
        # Reduced history limit to mitigate rate limit and token limit errors
        history = self.db.history(limit=7) 
        messages: List[Dict[str, str]] = []

        for h in history:
            messages.append(
                {
                    "role": h["role"],
                    "content": h["content"],
                }
            )

        messages.append(
            {
                "role": "user",
                "content": user_text,
            }
        )
        return messages

    def _handle_tool(self, tool_call: Dict[str, Any]) -> str:
        tool_name = tool_call.get("tool")
        args = tool_call.get("args", {})

        if not isinstance(args, dict):
            args = {}

        if tool_name == "open_app" and "name" not in args and "app_name" in args:
            args["name"] = args["app_name"]

        try:
            result = self.tools.execute(tool_name, args)
            return str(result)
        except Exception as e:
            return f"Ошибка инструмента {tool_name}: {e}"

    def respond(self, user_text: str) -> str:
        messages = self._build_messages(user_text)

        reply = self.llm.chat(
            messages=messages,
            system=self._system_prompt(),
        )

        if not reply:
            return "Пустой ответ модели."

        reply = reply.strip()

        try:
            data = json.loads(reply)

            if isinstance(data, dict) and data.get("type") == "tool_call":
                tool_result = self._handle_tool(data)

                follow_messages = messages + [
                    {
                        "role": "assistant",
                        "content": reply,
                    },
                    {
                        "role": "user",
                        "content": f"Результат инструмента: {tool_result}. Сформируй короткий ответ пользователю.",
                    },
                ]

                final = self.llm.chat(
                    messages=follow_messages,
                    system=self._system_prompt(),
                )

                self.db.save_message("user", user_text, self.state.session_id)
                self.db.save_message("assistant", final, self.state.session_id)

                return final

        except Exception:
            pass

        self.db.save_message("user", user_text, self.state.session_id)
        self.db.save_message("assistant", reply, self.state.session_id)

        return reply