"""TemplateResolver — loads template files and registry."""

import json
import shutil
from pathlib import Path

TEMPLATES_ROOT = Path(__file__).parent / "templates"


def get_registry() -> dict:
    p = TEMPLATES_ROOT / "registry.json"
    if p.exists():
        return json.loads(p.read_text())
    return {}


def template_exists(space_type: str, template_id: str) -> bool:
    return (TEMPLATES_ROOT / space_type / template_id).is_dir()


def get_template_meta(space_type: str, template_id: str) -> dict:
    p = TEMPLATES_ROOT / space_type / template_id / "template.json"
    if p.exists():
        return json.loads(p.read_text())
    return {}


def copy_template_files(space_type: str, template_id: str, dest: Path) -> list[str]:
    """Copy template files to dest/files/, return list of filenames."""
    src = TEMPLATES_ROOT / space_type / template_id
    if not src.is_dir():
        raise FileNotFoundError(f"Template not found: {space_type}/{template_id}")
    dest_files = dest / "files"
    dest_files.mkdir(parents=True, exist_ok=True)
    copied = []
    for f in src.iterdir():
        if f.name == "template.json":
            continue
        shutil.copy2(f, dest_files / f.name)
        copied.append(f.name)
    return copied
