# utils.py
from datetime import datetime
from pathlib import Path
import hashlib
import json

from config import LOG_FILE


def now_str() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_json_load(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def safe_json_save(path: Path, data) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def append_log(text: str) -> None:
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{now_str()}] {text}\n")
