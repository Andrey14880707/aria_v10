"""FileEngine — safe read/write for Space files."""

from pathlib import Path


def _resolve(space_dir: Path, rel_path: str) -> Path:
    # Prevent path traversal
    target = (space_dir / "files" / rel_path).resolve()
    allowed = (space_dir / "files").resolve()
    if not str(target).startswith(str(allowed)):
        raise PermissionError(f"Path traversal blocked: {rel_path}")
    return target


def read_file(space_dir: Path, rel_path: str) -> str:
    p = _resolve(space_dir, rel_path)
    if not p.exists():
        raise FileNotFoundError(rel_path)
    return p.read_text(encoding="utf-8")


def write_file(space_dir: Path, rel_path: str, content: str) -> None:
    p = _resolve(space_dir, rel_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def delete_file(space_dir: Path, rel_path: str) -> None:
    p = _resolve(space_dir, rel_path)
    if not p.exists():
        raise FileNotFoundError(rel_path)
    p.unlink()
    # Remove empty parent dirs up to files/
    files_root = (space_dir / "files").resolve()
    parent = p.parent
    while parent != files_root and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent


def write_bytes(space_dir: Path, rel_path: str, data: bytes) -> None:
    p = _resolve(space_dir, rel_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def list_files(space_dir: Path) -> list[dict]:
    files_dir = space_dir / "files"
    if not files_dir.exists():
        return []
    result = []
    for f in sorted(files_dir.rglob("*")):
        if f.is_file():
            rel = f.relative_to(files_dir).as_posix()
            result.append({"path": rel, "size": f.stat().st_size})
    return result
