# parser.py
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from db import MemoryDB
from state import AgentState

TOOL_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def parse_tool_calls(text: str) -> List[Dict[str, Any]]:
    calls = []
    for block in TOOL_BLOCK_RE.findall(text):
        try:
            obj = json.loads(block)
            if obj.get("type") == "tool_call":
                calls.append(obj)
        except Exception:
            continue
    return calls


def strip_tool_blocks(text: str) -> str:
    return TOOL_BLOCK_RE.sub("", text).strip()


def parse_state_block(text: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    match = re.search(r"\[STATE\](.*?)\[/STATE\]", text, re.DOTALL)
    if not match:
        return text.strip(), None

    state_text = match.group(1).strip()
    clean_text = (text[:match.start()] + text[match.end():]).strip()

    try:
        data = json.loads(state_text)
        return clean_text, data
    except Exception:
        return clean_text, None


def apply_state_block(data: Optional[Dict[str, Any]], state: AgentState, db: MemoryDB) -> None:
    if not data:
        return

    if "face" in data and isinstance(data["face"], str):
        state.face = data["face"]

    if "energy" in data:
        try:
            state.energy += int(data["energy"])
        except Exception:
            pass

    if "mood" in data:
        try:
            state.mood += int(data["mood"])
        except Exception:
            pass

    if "hunger" in data:
        try:
            state.hunger += int(data["hunger"])
        except Exception:
            pass

    if "thought" in data and data["thought"] is not None:
        state.last_thought = str(data["thought"])[:120]

    if "fact" in data and data["fact"]:
        db.add_fact(str(data["fact"])[:500], source="model")

    state.clamp()
