# config.py
from pathlib import Path
import os
import json

APP_NAME = "ARIA v9"
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

HOME = Path.home()
APP_DIR = HOME / ".aria_v9"
DB_FILE = APP_DIR / "aria.db"
LOG_FILE = APP_DIR / "aria.log"
BACKUP_DIR = APP_DIR / "backups"
NOTES_FILE = APP_DIR / "notes.txt"
PHOTO_FILE = APP_DIR / "photo.jpg"
CONFIG_FILE = APP_DIR / "config.json"

APP_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "owner_name": "Андрей",
    "background_enabled": True,
    "background_interval_sec": 180,
    "max_history_messages": 30,
    "max_tool_result_chars": 1000,
    "dangerous_tools_require_confirmation": True,
    "allow_network_tools": True,
    "allow_camera_tools": True,
    "allow_termux_tools": True,
    "allow_file_write_tools": True,
}

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged = DEFAULT_CONFIG.copy()
                merged.update(data)
                return merged
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(data: dict) -> None:
    tmp = CONFIG_FILE.with_suffix(CONFIG_FILE.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_FILE)

CONFIG = load_config()
save_config(CONFIG)
