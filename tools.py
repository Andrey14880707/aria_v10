# tools.py
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import requests

from config import CONFIG, HOME, NOTES_FILE, PHOTO_FILE
from db import MemoryDB
from safety import SafetyPolicy, ToolPolicyError
from state import AgentState


class ToolRunner:
    def __init__(self, state: AgentState, db: MemoryDB):
        self.state = state
        self.db = db

    def _run(self, argv: List[str], timeout: int = 20) -> str:
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            out = (proc.stdout + proc.stderr).strip()
            return out or "✓"
        except subprocess.TimeoutExpired:
            return "⏱ timeout"
        except Exception as e:
            return f"⚠ {e}"

    def _termux_allowed(self) -> None:
        if not CONFIG.get("allow_termux_tools", True):
            raise ToolPolicyError("termux_tools_disabled")

    def _network_allowed(self) -> None:
        if not CONFIG.get("allow_network_tools", True):
            raise ToolPolicyError("network_tools_disabled")

    def _write_allowed(self) -> None:
        if not CONFIG.get("allow_file_write_tools", True):
            raise ToolPolicyError("file_write_tools_disabled")

    def execute(self, tool_name: str, args: Dict[str, Any]) -> str:
        SafetyPolicy.ensure_tool_allowed(tool_name)

        fn = getattr(self, f"tool_{tool_name}", None)
        if not fn:
            raise ToolPolicyError(f"tool_not_found:{tool_name}")

        result = fn(args if isinstance(args, dict) else {})
        self.state.commands_run += 1

        self.db.add_tool_event(
            self.state.session_id,
            tool_name,
            json.dumps(args, ensure_ascii=False),
            str(result)[:4000],
            "ok",
        )
        return result

    # ===== базовые termux api =====

    def tool_battery_status(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        return self._run(["termux-battery-status"])

    def tool_location(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        provider = str(args.get("provider", "gps")).strip()
        request = ["termux-location"]
        if provider in {"gps", "network", "passive"}:
            request += ["-p", provider]
        return self._run(request)

    def tool_camera_photo(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        out_path = str(args.get("path", PHOTO_FILE)).strip()
        return self._run(["termux-camera-photo", out_path], timeout=30)

    def tool_torch(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        state = str(args.get("state", "on")).strip().lower()
        if state not in {"on", "off"}:
            raise ToolPolicyError("invalid_torch_state")
        return self._run(["termux-torch", state])

    def tool_speak(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        text = str(args.get("text", "")).strip()
        if not text:
            raise ToolPolicyError("empty_text")
        return self._run(["termux-tts-speak", text])

    def tool_notification(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        title = str(args.get("title", "ARIA")).strip()
        content = str(args.get("content", "")).strip()
        return self._run([
            "termux-notification",
            "--title", title,
            "--content", content
        ])

    def tool_toast(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        text = str(args.get("text", "")).strip()
        if not text:
            raise ToolPolicyError("empty_text")
        return self._run(["termux-toast", text])

    def tool_vibrate(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        duration = str(int(args.get("duration", 300)))
        return self._run(["termux-vibrate", "-d", duration])

    def tool_clipboard_get(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        return self._run(["termux-clipboard-get"])

    def tool_clipboard_set(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        text = str(args.get("text", "")).strip()
        if not text:
            raise ToolPolicyError("empty_text")
        return self._run(["termux-clipboard-set", text])

    def tool_wifi_info(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        return self._run(["termux-wifi-connectioninfo"])

    def tool_telephony_info(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        return self._run(["termux-telephony-deviceinfo"])

    def tool_volume(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        stream = str(args.get("stream", "music")).strip()
        value = str(int(args.get("value", 5)))
        return self._run(["termux-volume", stream, value])

    def tool_sensor(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        sensor = str(args.get("sensor", "")).strip()
        delay = str(args.get("delay", "normal")).strip()
        if sensor:
            return self._run(["termux-sensor", "-s", sensor, "-d", delay], timeout=25)
        return self._run(["termux-sensor", "-d", delay], timeout=25)

    def tool_sms_send(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        number = str(args.get("number", "")).strip()
        text = str(args.get("text", "")).strip()
        if not number or not text:
            raise ToolPolicyError("missing_number_or_text")
        return self._run(["termux-sms-send", "-n", number, text], timeout=20)

    def tool_call_log(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        return self._run(["termux-call-log"], timeout=20)

    def tool_contact_list(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        return self._run(["termux-contact-list"], timeout=20)

    def tool_media_info(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        return self._run(["termux-media-player", "info"], timeout=15)

    def tool_media_play(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        file_path = str(args.get("path", "")).strip()
        if not file_path:
            raise ToolPolicyError("missing_path")
        return self._run(["termux-media-player", "play", file_path], timeout=20)

    def tool_media_control(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        action = str(args.get("action", "")).strip()
        allowed = {"play", "pause", "stop", "info"}
        if action not in allowed:
            raise ToolPolicyError("invalid_media_action")
        return self._run(["termux-media-player", action], timeout=15)

    def tool_share(self, args: Dict[str, Any]) -> str:
        self._termux_allowed()
        text = str(args.get("text", "")).strip()
        if not text:
            raise ToolPolicyError("empty_text")
        return self._run(["termux-share", "-a", "send", text], timeout=20)

    # ===== сеть / файлы =====

    def tool_weather(self, args: Dict[str, Any]) -> str:
        self._network_allowed()
        city = str(args.get("city", "Hamar")).strip()
        r = requests.get(f"https://wttr.in/{requests.utils.quote(city)}?format=3", timeout=10)
        return r.text.strip()[:500]

    def tool_internet_search(self, args: Dict[str, Any]) -> str:
        self._network_allowed()
        query = str(args.get("query", "")).strip()
        if not query:
            raise ToolPolicyError("empty_query")

        r = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1,
            },
            timeout=15,
        )
        data = r.json()
        text = data.get("AbstractText") or data.get("Answer") or ""

        if not text:
            related = data.get("RelatedTopics", [])
            parts = []
            for item in related[:5]:
                if isinstance(item, dict) and item.get("Text"):
                    parts.append(item["Text"])
            text = "\n".join(parts) if parts else "Нет прямого ответа."

        return text[:1200]

    def tool_http_get(self, args: Dict[str, Any]) -> str:
        self._network_allowed()
        url = str(args.get("url", "")).strip()
        if not url:
            raise ToolPolicyError("missing_url")
        r = requests.get(url, timeout=20)
        return r.text[:4000]

    def tool_download_file(self, args: Dict[str, Any]) -> str:
        self._network_allowed()
        self._write_allowed()

        url = str(args.get("url", "")).strip()
        path = str(args.get("path", "")).strip()
        if not url or not path:
            raise ToolPolicyError("missing_url_or_path")

        out_path = Path(path).expanduser().resolve()
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(r.content)
        return f"Файл скачан: {out_path}"

    def tool_list_dir(self, args: Dict[str, Any]) -> str:
        path = Path(str(args.get("path", HOME))).expanduser().resolve()
        if not path.exists():
            return "Путь не существует."
        if not path.is_dir():
            return "Это не папка."

        items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        return "\n".join([i.name + ("/" if i.is_dir() else "") for i in items[:200]])

    def tool_read_file(self, args: Dict[str, Any]) -> str:
        path = str(args.get("path", "")).strip()
        if not path:
            raise ToolPolicyError("missing_path")
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return "Файл не найден."
        if p.is_dir():
            return "Это папка."
        return p.read_text(encoding="utf-8", errors="ignore")[:8000]

    def tool_read_notes(self, args: Dict[str, Any]) -> str:
        if not NOTES_FILE.exists():
            return "Заметок пока нет."
        return NOTES_FILE.read_text(encoding="utf-8")[:4000]

    def tool_append_note(self, args: Dict[str, Any]) -> str:
        self._write_allowed()
        text = str(args.get("text") or args.get("note") or args.get("content") or "").strip()
        if not text:
            raise ToolPolicyError("empty_note")
        with open(NOTES_FILE, "a", encoding="utf-8") as f:
            f.write(text + "\n")
        self.db.add_note(text)
        return f"Заметка сохранена: {text}"

    # ===== безопасные заглушки вместо невозможного =====

    def tool_open_app(self, args: Dict[str, Any]) -> str:
        name = str(args.get("name") or args.get("app_name") or args.get("package") or "").strip()
        return (
            f"Прямой запуск приложения '{name}' из Termux без root/ADB/Accessibility недоступен. "
            f"Нужен Accessibility Service или другой уровень доступа."
        )

    def tool_tap(self, args: Dict[str, Any]) -> str:
        return "Тапы по экрану из обычного Termux без повышенных прав недоступны."

    def tool_swipe(self, args: Dict[str, Any]) -> str:
        return "Свайпы из обычного Termux без повышенных прав недоступны."

    def tool_input_text(self, args: Dict[str, Any]) -> str:
        return "Ввод текста в чужие приложения без Accessibility/root недоступен."

    def tool_keyevent(self, args: Dict[str, Any]) -> str:
        return "Системные keyevent из обычного Termux ограничены Android sandbox."

    def tool_screenshot(self, args: Dict[str, Any]) -> str:
        return "Полноценный screencap из обычного Termux на этом устройстве ограничен. Нужен другой способ доступа."

    def tool_get_screen_size(self, args: Dict[str, Any]) -> str:
        return "Чтение параметров экрана через системные shell-команды на этом устройстве ограничено."

    def tool_get_current_app(self, args: Dict[str, Any]) -> str:
        return "Определение текущего приложения через dumpsys из обычного Termux недоступно."

    def tool_open_settings(self, args: Dict[str, Any]) -> str:
        return "Прямой запуск системных settings intent через shell на этом устройстве ограничен."

    def tool_run_termux_intent(self, args: Dict[str, Any]) -> str:
        return "Произвольные Android intent через shell здесь ограничены системой безопасности."

    def tool_list_packages(self, args: Dict[str, Any]) -> str:
        return "Чтение списка пакетов через pm list packages из обычного Termux на этом устройстве ограничено."

    def tool_system_info(self, args: Dict[str, Any]) -> str:
        parts = [
            self._run(["uname", "-a"]),
            self._run(["uptime"]),
            self._run(["df", "-h"]),
        ]
        return "\n\n".join(parts)[:2500]

    def tool_sleep(self, args: Dict[str, Any]) -> str:
        import time
        seconds = float(args.get("seconds", 1))
        if seconds < 0 or seconds > 10:
            raise ToolPolicyError("invalid_sleep_seconds")
        time.sleep(seconds)
        return f"Подождал {seconds} сек."

    def tool_echo(self, args: Dict[str, Any]) -> str:
        return str(args.get("text", ""))
