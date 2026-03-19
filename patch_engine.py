"""PatchEngine — applies LLM-generated patches to Space files."""

import json
import re
from pathlib import Path

from file_engine import read_file, write_file, list_files


# ── System prompt for patch requests ────────────────────────────────────────

PATCH_SYSTEM = """You are a code patch engine for ARIA Open Space.
You receive:
- The user's change request
- Current file contents (all files of the space)

Respond ONLY with a JSON array of file patches. No explanation, no markdown.

Format:
[
  {
    "path": "index.html",
    "action": "replace",
    "content": "<entire new file content>"
  }
]

Actions:
- "replace": overwrite entire file with new content
- "append": append content to end of file

Rules:
- Always return valid JSON
- Include only files that need changes
- Preserve existing functionality unless explicitly asked to change it
- For HTML/JS games, keep everything self-contained in the files
"""


def build_patch_prompt(space_dir: Path, user_prompt: str) -> str:
    files = list_files(space_dir)
    parts = [f"User request: {user_prompt}\n\nCurrent files:"]
    for f in files:
        try:
            content = read_file(space_dir, f["path"])
            parts.append(f"\n--- {f['path']} ---\n{content}")
        except Exception:
            pass
    return "\n".join(parts)


def apply_patch_response(space_dir: Path, llm_response: str, version: int) -> list[str]:
    """Parse LLM JSON response and write files. Returns list of modified paths."""
    # Strip markdown code fences if present
    text = llm_response.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        patches = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON array from text
        m = re.search(r"\[[\s\S]*\]", text)
        if m:
            patches = json.loads(m.group())
        else:
            raise ValueError("LLM did not return valid JSON patch array")

    if not isinstance(patches, list):
        raise ValueError("Patch response must be a JSON array")

    modified = []
    for patch in patches:
        if not isinstance(patch, dict):
            continue
        path = patch.get("path", "")
        action = patch.get("action", "replace")
        content = patch.get("content", "")
        if not path:
            continue

        if action == "replace":
            write_file(space_dir, path, content)
        elif action == "append":
            try:
                existing = read_file(space_dir, path)
                write_file(space_dir, path, existing + "\n" + content)
            except FileNotFoundError:
                write_file(space_dir, path, content)

        modified.append(path)

    return modified
