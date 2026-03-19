# tools_shell.py — Allowlisted shell/file/git tool execution for ARIA
"""
Provides 8 safe, allowlisted tools:
  run_shell   — execute whitelisted commands only
  read_file   — read text file with line limit
  write_file  — write text to file (safe paths only)
  list_dir    — list directory contents
  git_status  — git status in a repo
  git_add     — stage files for commit
  git_commit  — create a commit
  git_push    — push to remote (CI trigger)

All calls are logged. Dangerous patterns are rejected before execution.
"""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import HOME
from utils import append_log

# ── safe roots ────────────────────────────────────────────────────────────────

_SAFE_READ_ROOTS: tuple[str, ...] = (
    str(HOME),
    "/sdcard",
    "/storage/emulated/0",
    "/data/data/com.termux/files/home",
)

_SAFE_WRITE_ROOTS: tuple[str, ...] = (
    str(HOME),
    "/sdcard",
    "/storage/emulated/0",
    "/data/data/com.termux/files/home",
)

_BLOCKED_PATHS: tuple[str, ...] = (
    "/system",
    "/vendor",
    "/proc",
    "/dev/",
    "/sys",
    "/data/system",
    "/etc/passwd",
    "/etc/shadow",
)

# ── run_shell allowlist ───────────────────────────────────────────────────────

# Only these executable names may be the first token of a run_shell command.
ALLOWED_EXECUTABLES: frozenset[str] = frozenset({
    # filesystem (read-only)
    "ls", "ll", "la", "pwd", "cat", "head", "tail", "wc",
    "stat", "file", "du", "df", "find", "diff", "sort", "uniq",
    "md5sum", "sha256sum",
    # text processing (non-destructive)
    "grep", "egrep", "fgrep", "rg", "awk", "sed", "cut", "tr",
    # system info
    "echo", "date", "uname", "whoami", "id", "hostname",
    "env", "printenv", "ps", "free", "uptime", "lscpu",
    # development
    "git", "python", "python3", "pip", "pip3",
    "flutter", "dart", "node", "npm", "which", "type",
    # termux
    "termux-battery-status", "termux-info", "termux-wifi-connectioninfo",
    "pkg",
    # network read-only
    "ping", "curl", "wget",
})

# Patterns that are always rejected regardless of executable
_DANGEROUS_RE: list[re.Pattern[str]] = [
    re.compile(r";\s*[a-zA-Z]"),           # command chaining via ;
    re.compile(r"\|\s*(?:sh|bash|zsh|python\d?|perl|ruby|node|eval)"),
    re.compile(r"`[^`]+`"),                 # backtick subshell
    re.compile(r"\$\([^)]+\)"),            # $() subshell
    re.compile(r">\s*/(?!dev/null)"),      # redirect to absolute path
    re.compile(r">>\s*/(?!dev/null)"),     # append to absolute path
    re.compile(r"\|\s*tee\s+/"),           # pipe+tee to absolute path
    re.compile(r"--exec(?:dir)?\s+sh"),    # find --exec sh
    re.compile(r"\bsudo\b|\bsu\s"),        # privilege escalation
    re.compile(r"\bbase64\s+-d"),          # base64 decode injection
    re.compile(r"\beval\b"),               # eval
    re.compile(r"\bsource\s"),             # source
    re.compile(r"&&\s*(?:rm|mkfs|dd\s|shred)"),  # chain to destructive
    re.compile(r"\brm\s+-rf?\s*/"),        # rm -r /
    re.compile(r":(\s*)\{(\s*):(\s*)\|"),  # fork bomb
    re.compile(r"chmod\s+[0-9]*[67][0-9]"), # chmod to world-writable
    re.compile(r"\bchown\b"),               # chown
    re.compile(r"\bmkfs\b|\bdd\s+if="),    # disk operations
]


# ── helper ────────────────────────────────────────────────────────────────────

def _check_dangerous(command: str) -> None:
    """Raise ValueError if any dangerous pattern is found."""
    for pattern in _DANGEROUS_RE:
        if pattern.search(command):
            raise ValueError(f"Rejected: dangerous pattern [{pattern.pattern}]")


def _check_executable(command: str) -> None:
    """Raise ValueError if first token is not in ALLOWED_EXECUTABLES."""
    try:
        tokens = shlex.split(command)
    except ValueError as e:
        raise ValueError(f"Cannot parse command: {e}")
    if not tokens:
        raise ValueError("Empty command")
    exe = Path(tokens[0]).name  # strip path prefix
    if exe not in ALLOWED_EXECUTABLES:
        raise ValueError(
            f"Executable '{exe}' not in allowlist. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXECUTABLES))}"
        )


def _safe_read_path(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    for blocked in _BLOCKED_PATHS:
        if str(p).startswith(blocked):
            raise PermissionError(f"Path blocked: {p}")
    return p


def _safe_write_path(path: str) -> Path:
    p = Path(path).expanduser().resolve()
    for blocked in _BLOCKED_PATHS:
        if str(p).startswith(blocked):
            raise PermissionError(f"Path blocked: {p}")
    if not any(str(p).startswith(root) for root in _SAFE_WRITE_ROOTS):
        raise PermissionError(
            f"Write path '{p}' is outside safe roots: {_SAFE_WRITE_ROOTS}"
        )
    return p


def _run(argv: list[str], cwd: Optional[str], timeout: int) -> str:
    """Execute a pre-validated argv list and return stdout+stderr."""
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=cwd or str(HOME),
        )
        out = (proc.stdout + proc.stderr).strip()
        return out if out else "✓ (no output)"
    except subprocess.TimeoutExpired:
        return f"⏱ Timed out after {timeout}s"
    except FileNotFoundError as e:
        return f"⚠ Not found: {e}"
    except Exception as e:
        return f"⚠ {e}"


# ── public tool functions ─────────────────────────────────────────────────────

def run_shell(
    command: str,
    cwd: Optional[str] = None,
    timeout: int = 30,
) -> str:
    """Execute an allowlisted shell command."""
    append_log(f"[run_shell] command={command!r} cwd={cwd}")
    _check_dangerous(command)
    _check_executable(command)

    try:
        argv = shlex.split(command)
    except ValueError as e:
        return f"⚠ Parse error: {e}"

    safe_cwd: Optional[str] = None
    if cwd:
        try:
            safe_cwd = str(_safe_read_path(cwd))
        except PermissionError as e:
            return f"⚠ {e}"

    result = _run(argv, safe_cwd, min(timeout, 60))
    append_log(f"[run_shell] result={result[:200]}")
    return result


def read_file(path: str, max_lines: int = 200) -> str:
    """Read text file content (limited to max_lines)."""
    append_log(f"[read_file] path={path!r}")
    try:
        p = _safe_read_path(path)
        if not p.exists():
            return f"⚠ File not found: {p}"
        if p.is_dir():
            return f"⚠ Is a directory: {p}. Use list_dir instead."
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        if len(lines) > max_lines:
            head = "\n".join(lines[:max_lines])
            return f"{head}\n…[truncated, {len(lines)} total lines]"
        return text if text else "(empty file)"
    except PermissionError as e:
        return f"⚠ {e}"
    except Exception as e:
        return f"⚠ {e}"


def write_file(path: str, content: str, append: bool = False) -> str:
    """Write or append content to a file (safe paths only)."""
    append_log(f"[write_file] path={path!r} append={append} len={len(content)}")
    try:
        p = _safe_write_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if append:
            with p.open("a", encoding="utf-8") as f:
                f.write(content)
            return f"✓ Appended {len(content)} chars to {p}"
        else:
            p.write_text(content, encoding="utf-8")
            return f"✓ Wrote {len(content)} chars to {p}"
    except PermissionError as e:
        return f"⚠ {e}"
    except Exception as e:
        return f"⚠ {e}"


def list_dir(path: str) -> str:
    """List directory contents (name, type, size)."""
    append_log(f"[list_dir] path={path!r}")
    try:
        p = _safe_read_path(path)
        if not p.exists():
            return f"⚠ Path not found: {p}"
        if not p.is_dir():
            return f"⚠ Not a directory: {p}"
        entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        if not entries:
            return "(empty directory)"
        lines = []
        for e in entries[:200]:
            try:
                size = e.stat().st_size if e.is_file() else ""
                kind = "DIR " if e.is_dir() else "FILE"
                size_str = f"  {size:>10} B" if size != "" else ""
                lines.append(f"{kind}  {e.name}{size_str}")
            except Exception:
                lines.append(f"????  {e.name}")
        if len(entries) > 200:
            lines.append(f"… ({len(entries) - 200} more entries)")
        return "\n".join(lines)
    except PermissionError as e:
        return f"⚠ {e}"
    except Exception as e:
        return f"⚠ {e}"


# ── git tools ─────────────────────────────────────────────────────────────────

def _git(args: list[str], repo_path: str, timeout: int = 30) -> str:
    """Run a git command in repo_path."""
    try:
        rp = _safe_read_path(repo_path)
    except PermissionError as e:
        return f"⚠ {e}"
    if not (rp / ".git").exists() and not rp.parent.joinpath(".git").exists():
        # Allow if anywhere in the tree
        pass
    return _run(["git"] + args, str(rp), timeout)


def git_status(repo_path: str = ".") -> str:
    append_log(f"[git_status] repo={repo_path}")
    return _git(["status", "--porcelain=v1", "--branch"], repo_path)


def git_add(files: List[str], repo_path: str = ".") -> str:
    """Stage specific files (never stages /system etc.)."""
    append_log(f"[git_add] files={files} repo={repo_path}")
    if not files:
        return "⚠ No files specified"
    # Validate every path
    safe_files: list[str] = []
    for f in files:
        f = f.strip()
        if not f:
            continue
        # Allow relative paths (git add handles resolution)
        if f.startswith("/"):
            try:
                _safe_write_path(f)
            except PermissionError as e:
                return f"⚠ {e}"
        safe_files.append(f)
    if not safe_files:
        return "⚠ No valid files after validation"
    return _git(["add", "--"] + safe_files, repo_path)


def git_commit(
    message: str,
    repo_path: str = ".",
    author_name: str = "ARIA",
    author_email: str = "aria@localhost",
) -> str:
    append_log(f"[git_commit] message={message!r} repo={repo_path}")
    if not message.strip():
        return "⚠ Commit message cannot be empty"
    # Sanitize message: no shell metacharacters
    safe_msg = re.sub(r"[`$\\]", "", message)[:500]
    return _git(
        [
            "-c", f"user.name={author_name}",
            "-c", f"user.email={author_email}",
            "commit", "-m", safe_msg,
        ],
        repo_path,
        timeout=30,
    )


def git_push(
    remote: str = "origin",
    branch: Optional[str] = None,
    repo_path: str = ".",
    timeout: int = 60,
) -> str:
    append_log(f"[git_push] remote={remote} branch={branch} repo={repo_path}")
    # Validate remote name: alphanumeric + - _ . only
    if not re.fullmatch(r"[A-Za-z0-9_.\-]+", remote):
        return f"⚠ Invalid remote name: {remote!r}"
    args = ["push", remote]
    if branch:
        if not re.fullmatch(r"[A-Za-z0-9_./\-]+", branch):
            return f"⚠ Invalid branch name: {branch!r}"
        args.append(branch)
    return _git(args, repo_path, timeout=timeout)


# ── registry for /execute endpoint ───────────────────────────────────────────

SHELL_TOOLS: dict[str, Any] = {
    "run_shell": run_shell,
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
    "git_status": git_status,
    "git_add": git_add,
    "git_commit": git_commit,
    "git_push": git_push,
}


def execute_shell_tool(tool: str, args: Dict[str, Any]) -> str:
    """Dispatch a tool call from the /execute endpoint."""
    if tool not in SHELL_TOOLS:
        raise ValueError(
            f"Unknown tool '{tool}'. Available: {', '.join(sorted(SHELL_TOOLS))}"
        )
    fn = SHELL_TOOLS[tool]
    try:
        return fn(**args)
    except TypeError as e:
        raise ValueError(f"Invalid arguments for '{tool}': {e}") from e
