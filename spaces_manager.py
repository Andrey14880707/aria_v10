"""SpaceManager — create, load, list, delete, duplicate Spaces."""

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from artifact_classifier import classify
from template_resolver import copy_template_files, template_exists

# Store spaces OUTSIDE the project dir so uvicorn --reload doesn't
# trigger a server restart when space files (index.html, app.js, etc.) change.
_DEFAULT_ROOT = Path.home() / ".aria_v10" / "spaces"
SPACES_ROOT = Path(os.environ.get("ARIA_SPACES_DIR", str(_DEFAULT_ROOT)))
SPACES_ROOT.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _space_dir(space_id: str) -> Path:
    return SPACES_ROOT / space_id


def _load_manifest(space_id: str) -> dict:
    p = _space_dir(space_id) / "space.json"
    if not p.exists():
        raise FileNotFoundError(f"Space not found: {space_id}")
    return json.loads(p.read_text())


def _save_manifest(space_id: str, manifest: dict) -> None:
    p = _space_dir(space_id) / "space.json"
    p.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))


# ── Public API ────────────────────────────────────────────────────────────────

def create_space(prompt: str, name: Optional[str] = None) -> dict:
    space_id = "space_" + uuid.uuid4().hex[:8]
    space_type, template = classify(prompt)
    now = _now()
    space_dir = _space_dir(space_id)
    space_dir.mkdir(parents=True, exist_ok=True)
    (space_dir / "history").mkdir(exist_ok=True)
    (space_dir / "logs").mkdir(exist_ok=True)

    # Determine entrypoint from template or default
    entrypoint = "index.html"
    if space_type == "code_tool":
        entrypoint = "main.py"

    manifest = {
        "id": space_id,
        "name": name or _default_name(prompt),
        "description": prompt,
        "type": space_type,
        "template": template,
        "version": 1,
        "entrypoint": entrypoint,
        "stack": _stack_for(space_type),
        "status": "created",
        "created_from_prompt": prompt,
        "created_at": now,
        "updated_at": now,
        "features": {
            "preview": space_type == "web_app",
            "editable": True,
            "exportable": True,
            "buildable": False,
        },
        "permissions": [],
        "tags": [],
        "runtime": {"port": None, "status": "stopped"},
    }

    # Copy template files if available
    if template_exists(space_type, template):
        copy_template_files(space_type, template, space_dir)
        manifest["status"] = "ready"

    _save_manifest(space_id, manifest)
    return manifest


def get_space(space_id: str) -> dict:
    return _load_manifest(space_id)


def list_spaces() -> list[dict]:
    result = []
    if not SPACES_ROOT.exists():
        return result
    for d in sorted(SPACES_ROOT.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        manifest_path = d / "space.json"
        if manifest_path.exists():
            try:
                m = json.loads(manifest_path.read_text())
                result.append({
                    "id": m.get("id", d.name),
                    "name": m.get("name", d.name),
                    "type": m.get("type", ""),
                    "status": m.get("status", ""),
                    "updated_at": m.get("updated_at", ""),
                })
            except Exception:
                pass
    return result


def update_space(space_id: str, updates: dict) -> dict:
    manifest = _load_manifest(space_id)
    manifest.update(updates)
    manifest["updated_at"] = _now()
    _save_manifest(space_id, manifest)
    return manifest


def delete_space(space_id: str) -> None:
    d = _space_dir(space_id)
    if not d.exists():
        raise FileNotFoundError(f"Space not found: {space_id}")
    shutil.rmtree(d)


def duplicate_space(space_id: str, new_name: Optional[str] = None) -> dict:
    src = _space_dir(space_id)
    original = _load_manifest(space_id)
    new_id = "space_" + uuid.uuid4().hex[:8]
    dst = _space_dir(new_id)
    shutil.copytree(src, dst)
    now = _now()
    manifest = json.loads((dst / "space.json").read_text())
    manifest["id"] = new_id
    manifest["name"] = new_name or (original.get("name", "") + " (copy)")
    manifest["created_at"] = now
    manifest["updated_at"] = now
    manifest["runtime"] = {"port": None, "status": "stopped"}
    (dst / "space.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return manifest


def bump_version(space_id: str, snapshot: Optional[dict] = None) -> int:
    """Increment version, optionally saving a history snapshot."""
    manifest = _load_manifest(space_id)
    v = manifest.get("version", 1)
    if snapshot:
        hist_file = _space_dir(space_id) / "history" / f"v{v}.json"
        hist_file.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
    manifest["version"] = v + 1
    manifest["updated_at"] = _now()
    _save_manifest(space_id, manifest)
    return manifest["version"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_name(prompt: str) -> str:
    words = prompt.split()[:4]
    return " ".join(w.capitalize() for w in words)


def _stack_for(space_type: str) -> dict:
    if space_type == "web_app":
        return {"frontend": "html_css_js", "backend": "none", "runtime": "webview"}
    if space_type == "code_tool":
        return {"frontend": "none", "backend": "python", "runtime": "subprocess"}
    return {"frontend": "none", "backend": "none", "runtime": "none"}
