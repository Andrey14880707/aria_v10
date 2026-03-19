# router.py — FastAPI REST backend for ARIA v10
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import CONFIG, MODEL, HOME, save_config
from db import MemoryDB
from state import AgentState
from tools import ToolRunner
from tools_shell import SHELL_TOOLS, execute_shell_tool
from utils import append_log
try:
    import spaces_manager as _sm
    import file_engine as _fe
    from patch_engine import PATCH_SYSTEM, build_patch_prompt, apply_patch_response
    _SPACES_OK = True
except Exception as _spaces_import_err:
    _sm = None  # type: ignore
    _fe = None  # type: ignore
    _SPACES_OK = False
    _spaces_import_err_msg = str(_spaces_import_err)
    import traceback as _tb
    print(f"[ARIA] spaces modules failed to load: {_spaces_import_err}\n{_tb.format_exc()}")

# ── LLM providers ─────────────────────────────────────────────────────────────

try:
    from llm_providers.anthropic import AnthropicProvider
except Exception:
    AnthropicProvider = None  # type: ignore

try:
    from llm_providers.openai import OpenAIProvider
except Exception:
    OpenAIProvider = None  # type: ignore

try:
    from llm_providers.gemini import GeminiProvider
except Exception:
    GeminiProvider = None  # type: ignore

# ── Singleton session ─────────────────────────────────────────────────────────

_db = MemoryDB()
_state = AgentState()
_state.session_id = _db.start_session()
_tools = ToolRunner(_state, _db)

try:
    from llm import AnthropicClient
    _llm = AnthropicClient()
except Exception:
    _llm = None  # type: ignore

try:
    from agent import Agent
    _agent: Optional[Agent] = Agent(_llm, _db, _state, _tools) if _llm else None
except Exception:
    _agent = None

# ── FastAPI ───────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ARIA Backend",
    description="Local AI assistant REST API — v10",
    version="10.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request / Response models ─────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    provider: str = "anthropic"
    model: str = MODEL


class ChatResponse(BaseModel):
    reply: str
    provider: str
    model: str
    commands_run: int
    session_id: int


class ExecuteRequest(BaseModel):
    tool: str
    args: Dict[str, Any] = {}


class ExecuteResponse(BaseModel):
    tool: str
    result: str
    status: str  # "ok" | "error"


class BuildApkRequest(BaseModel):
    message: str = "ARIA: automated build trigger"
    files: List[str] = []          # if empty → git add -A (restricted to safe paths)
    remote: str = "origin"
    branch: Optional[str] = None
    repo_path: str = "."


class BuildApkResponse(BaseModel):
    status: str
    steps: List[Dict[str, str]]    # [{step, output}]
    message: str


class SettingsRequest(BaseModel):
    owner_name: Optional[str] = None
    background_enabled: Optional[bool] = None
    allow_network_tools: Optional[bool] = None
    allow_camera_tools: Optional[bool] = None
    allow_termux_tools: Optional[bool] = None
    allow_file_write_tools: Optional[bool] = None
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None


class ToolExecRequest(BaseModel):
    tool: str
    args: Dict[str, Any] = {}


# ── Space models ─────────────────────────────────────────────────────────────

class SpaceCreateRequest(BaseModel):
    prompt: str
    name: Optional[str] = None


class SpacePatchRequest(BaseModel):
    prompt: str


class SpaceDuplicateRequest(BaseModel):
    name: Optional[str] = None


class SpaceFileWriteRequest(BaseModel):
    path: str
    content: str


class FactResponse(BaseModel):
    id: int
    fact: str
    created_at: str
    source: str


class NoteResponse(BaseModel):
    id: int
    note: str
    created_at: str


class MemoryStats(BaseModel):
    sessions: int
    facts: int
    commands_run: int
    background_cycles: int
    last_thought: str


class LogEntry(BaseModel):
    line: str


# ── Helpers ───────────────────────────────────────────────────────────────────

LOG_FILE = HOME / ".aria_v9" / "aria.log"


def _build_llm(provider: str, model: str):
    if provider == "openai" and OpenAIProvider:
        return OpenAIProvider(model=model)
    if provider == "gemini" and GeminiProvider:
        return GeminiProvider(model=model)
    # Default / anthropic
    if AnthropicProvider:
        return AnthropicProvider(model=model)
    from llm import AnthropicClient
    return AnthropicClient(model=model)


def _get_agent(provider: str, model: str):
    from agent import Agent
    current_prov = CONFIG.get("active_provider", "anthropic")
    if provider == current_prov and _agent is not None:
        return _agent, _db, _state
    db = MemoryDB()
    st = AgentState()
    st.session_id = db.start_session()
    tools = ToolRunner(st, db)
    llm = _build_llm(provider, model)
    return Agent(llm, db, st, tools), db, st


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "10.0.0",
        "session_id": _state.session_id,
        "commands_run": _state.commands_run,
    }


# ── Chat ──────────────────────────────────────────────────────────────────────


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "Empty message")
    try:
        ag, db, st = _get_agent(req.provider, req.model)
        reply = ag.respond(req.message)
        append_log(f"[API/chat] USER: {req.message[:200]}")
        append_log(f"[API/chat] ARIA: {reply[:300]}")
        return ChatResponse(
            reply=reply,
            provider=req.provider,
            model=req.model,
            commands_run=st.commands_run,
            session_id=st.session_id,
        )
    except Exception as e:
        append_log(f"[API/chat] ERROR: {e}")
        raise HTTPException(500, str(e))


# ── Execute (shell / file / git tools) ───────────────────────────────────────


@app.post("/execute", response_model=ExecuteResponse)
def execute(req: ExecuteRequest):
    """
    Execute one of the 8 allowlisted shell/file/git tools.
    Validates against SHELL_TOOLS registry before running.
    All calls are logged.
    """
    tool = req.tool.strip()
    append_log(f"[API/execute] tool={tool!r} args={json.dumps(req.args)[:200]}")

    try:
        result = execute_shell_tool(tool, req.args)
        append_log(f"[API/execute] ok result={result[:200]}")
        return ExecuteResponse(tool=tool, result=result, status="ok")
    except ValueError as e:
        append_log(f"[API/execute] rejected: {e}")
        raise HTTPException(400, str(e))
    except PermissionError as e:
        append_log(f"[API/execute] permission: {e}")
        raise HTTPException(403, str(e))
    except Exception as e:
        append_log(f"[API/execute] error: {e}")
        raise HTTPException(500, str(e))


# ── Build APK (git push → CI trigger) ────────────────────────────────────────


@app.post("/build_apk", response_model=BuildApkResponse)
def build_apk(req: BuildApkRequest):
    """
    Trigger APK rebuild via:
      1. git add  (specified files, or all tracked changes)
      2. git commit -m <message>
      3. git push  → triggers CI/CD (e.g. GitHub Actions)

    This does NOT build the APK on-device.
    The CI pipeline handles the actual build.
    """
    from tools_shell import git_add, git_commit, git_push, git_status

    append_log(f"[API/build_apk] msg={req.message!r} files={req.files}")
    steps: list[dict[str, str]] = []

    # Validate commit message
    if not req.message.strip():
        raise HTTPException(400, "Commit message cannot be empty")

    # 1. git status (pre-flight)
    status_out = git_status(req.repo_path)
    steps.append({"step": "git_status", "output": status_out})

    if "nothing to commit" in status_out and "nothing added" in status_out:
        return BuildApkResponse(
            status="skipped",
            steps=steps,
            message="Nothing to commit — working tree is clean.",
        )

    # 2. git add
    if req.files:
        add_out = git_add(req.files, req.repo_path)
    else:
        # Stage all tracked modifications (safe: excludes untracked secrets)
        from tools_shell import _run
        from config import HOME as _HOME
        add_out = _run(
            ["git", "add", "-u"],
            req.repo_path if req.repo_path != "." else str(Path(__file__).parent),
            30,
        )
    steps.append({"step": "git_add", "output": add_out})

    if add_out.startswith("⚠"):
        return BuildApkResponse(
            status="error",
            steps=steps,
            message=f"git add failed: {add_out}",
        )

    # 3. git commit
    commit_out = git_commit(
        message=req.message,
        repo_path=req.repo_path,
    )
    steps.append({"step": "git_commit", "output": commit_out})

    if commit_out.startswith("⚠") and "nothing to commit" not in commit_out:
        return BuildApkResponse(
            status="error",
            steps=steps,
            message=f"git commit failed: {commit_out}",
        )

    # 4. git push → CI trigger
    push_out = git_push(
        remote=req.remote,
        branch=req.branch,
        repo_path=req.repo_path,
        timeout=90,
    )
    steps.append({"step": "git_push", "output": push_out})

    ok = not push_out.startswith("⚠")
    append_log(f"[API/build_apk] push={'ok' if ok else 'fail'}: {push_out[:200]}")

    return BuildApkResponse(
        status="ok" if ok else "error",
        steps=steps,
        message=(
            "Changes pushed. CI will build the APK automatically."
            if ok
            else f"Push failed: {push_out}"
        ),
    )


# ── Open Space ────────────────────────────────────────────────────────────────

def _require_spaces():
    if not _SPACES_OK:
        raise HTTPException(503, f"Spaces module failed to load: {_spaces_import_err_msg}")


@app.get("/spaces/status")
def spaces_status():
    """Diagnostic endpoint — always returns, even if spaces modules are broken."""
    if _SPACES_OK:
        return {"ok": True, "spaces_root": str(_sm.SPACES_ROOT)}
    return {"ok": False, "error": _spaces_import_err_msg}


@app.post("/spaces/create")
def spaces_create(req: SpaceCreateRequest):
    _require_spaces()
    try:
        manifest = _sm.create_space(prompt=req.prompt, name=req.name)
        append_log(f"[spaces] created {manifest['id']} type={manifest['type']} template={manifest['template']}")
        return manifest
    except Exception as e:
        append_log(f"[spaces] create error: {e}")
        raise HTTPException(500, str(e))


@app.get("/spaces")
def spaces_list():
    _require_spaces()
    return _sm.list_spaces()


@app.get("/spaces/{space_id}")
def spaces_get(space_id: str):
    _require_spaces()
    try:
        return _sm.get_space(space_id)
    except FileNotFoundError:
        raise HTTPException(404, f"Space not found: {space_id}")


@app.delete("/spaces/{space_id}")
def spaces_delete(space_id: str):
    _require_spaces()
    try:
        _sm.delete_space(space_id)
        return {"status": "deleted", "id": space_id}
    except FileNotFoundError:
        raise HTTPException(404, f"Space not found: {space_id}")


@app.post("/spaces/{space_id}/duplicate")
def spaces_duplicate(space_id: str, req: SpaceDuplicateRequest):
    _require_spaces()
    try:
        manifest = _sm.duplicate_space(space_id, new_name=req.name)
        return manifest
    except FileNotFoundError:
        raise HTTPException(404, f"Space not found: {space_id}")


@app.post("/spaces/{space_id}/patch")
def spaces_patch(space_id: str, req: SpacePatchRequest):
    """Apply LLM-generated patch to Space files based on user prompt."""
    _require_spaces()
    try:
        manifest = _sm.get_space(space_id)
    except FileNotFoundError:
        raise HTTPException(404, f"Space not found: {space_id}")

    space_dir = _sm._space_dir(space_id)
    prompt_text = build_patch_prompt(space_dir, req.prompt)

    # Call LLM for patch
    try:
        ag, _, _ = _get_agent(
            CONFIG.get("active_provider", "anthropic"),
            CONFIG.get("active_model", MODEL),
        )
        # Build messages for raw LLM call (bypass agent tool loop)
        llm = _build_llm(
            CONFIG.get("active_provider", "anthropic"),
            CONFIG.get("active_model", MODEL),
        )
        response = llm.chat(
            messages=[{"role": "user", "content": prompt_text}],
            system=PATCH_SYSTEM,
            max_tokens=4096,
        )
    except Exception as e:
        raise HTTPException(500, f"LLM error: {e}")

    try:
        # Save snapshot before patching
        current_files: dict = {}
        for fi in _fe.list_files(space_dir):
            try:
                current_files[fi["path"]] = _fe.read_file(space_dir, fi["path"])
            except Exception:
                pass
        _sm.bump_version(space_id, snapshot={"files": current_files, "prompt": req.prompt})

        modified = apply_patch_response(space_dir, response, manifest.get("version", 1))
        _sm.update_space(space_id, {"status": "ready"})
        append_log(f"[spaces] patched {space_id} files={modified}")
        return {"status": "ok", "modified": modified, "space_id": space_id}
    except Exception as e:
        raise HTTPException(500, f"Patch error: {e}")


@app.get("/spaces/{space_id}/files")
def spaces_list_files(space_id: str):
    _require_spaces()
    try:
        _sm.get_space(space_id)  # existence check
    except FileNotFoundError:
        raise HTTPException(404, f"Space not found: {space_id}")
    space_dir = _sm._space_dir(space_id)
    return _fe.list_files(space_dir)


@app.get("/spaces/{space_id}/files/content")
def spaces_read_file(space_id: str, path: str):
    _require_spaces()
    try:
        _sm.get_space(space_id)
    except FileNotFoundError:
        raise HTTPException(404, f"Space not found: {space_id}")
    space_dir = _sm._space_dir(space_id)
    try:
        content = _fe.read_file(space_dir, path)
        return {"path": path, "content": content}
    except FileNotFoundError:
        raise HTTPException(404, f"File not found: {path}")
    except PermissionError as e:
        raise HTTPException(403, str(e))


@app.post("/spaces/{space_id}/files")
def spaces_write_file(space_id: str, req: SpaceFileWriteRequest):
    _require_spaces()
    try:
        _sm.get_space(space_id)
    except FileNotFoundError:
        raise HTTPException(404, f"Space not found: {space_id}")
    space_dir = _sm._space_dir(space_id)
    try:
        _fe.write_file(space_dir, req.path, req.content)
        _sm.update_space(space_id, {})  # bump updated_at
        return {"status": "ok", "path": req.path}
    except PermissionError as e:
        raise HTTPException(403, str(e))


@app.get("/spaces/{space_id}/templates")
def spaces_templates(_space_id: str):
    from template_resolver import get_registry
    return get_registry()


# ── Memory ────────────────────────────────────────────────────────────────────


@app.get("/memory", response_model=MemoryStats)
def memory_stats():
    return MemoryStats(
        sessions=_db.sessions_count(),
        facts=_db.facts_count(),
        commands_run=_state.commands_run,
        background_cycles=_state.background_cycles,
        last_thought=_state.last_thought,
    )


@app.get("/facts", response_model=List[FactResponse])
def get_facts(query: str = "", limit: int = 30):
    rows = _db.search_facts(query, limit=limit)
    return [
        FactResponse(
            id=r["id"],
            fact=r["fact"],
            created_at=r["created_at"],
            source=r.get("source", ""),
        )
        for r in rows
    ]


@app.get("/notes", response_model=List[NoteResponse])
def get_notes(limit: int = 30):
    rows = _db.recent_notes(limit)
    return [
        NoteResponse(id=r["id"], note=r["note"], created_at=r["created_at"])
        for r in rows
    ]


# ── Logs ──────────────────────────────────────────────────────────────────────


@app.get("/logs", response_model=List[LogEntry])
def get_logs(lines: int = 200):
    if not LOG_FILE.exists():
        return []
    try:
        text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
        all_lines = text.splitlines()
        return [LogEntry(line=ln) for ln in all_lines[-lines:]]
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Tools ─────────────────────────────────────────────────────────────────────


@app.get("/tools")
def list_tools():
    """Returns two categories of tools."""
    from safety import ALLOWED_TOOLS
    return {
        "shell_tools": sorted(SHELL_TOOLS.keys()),
        "agent_tools": sorted(ALLOWED_TOOLS),
    }


@app.post("/tools/execute")
def tools_execute_legacy(req: ToolExecRequest):
    """Legacy endpoint — executes agent (Termux) tools."""
    try:
        result = _tools.execute(req.tool, req.args)
        return {"result": result, "tool": req.tool, "status": "ok"}
    except Exception as e:
        raise HTTPException(400, str(e))


# ── Settings ──────────────────────────────────────────────────────────────────


@app.get("/settings")
def get_settings():
    safe = {k: v for k, v in CONFIG.items() if "key" not in k.lower()}
    safe["active_provider"] = CONFIG.get("active_provider", "anthropic")
    safe["active_model"] = CONFIG.get("active_model", MODEL)
    safe["anthropic_key_set"] = bool(
        os.environ.get("ANTHROPIC_API_KEY", CONFIG.get("anthropic_api_key", ""))
    )
    safe["openai_key_set"] = bool(
        os.environ.get("OPENAI_API_KEY", CONFIG.get("openai_api_key", ""))
    )
    safe["gemini_key_set"] = bool(
        os.environ.get("GEMINI_API_KEY", CONFIG.get("gemini_api_key", ""))
    )
    return safe


@app.post("/settings")
def update_settings(req: SettingsRequest):
    updates = req.model_dump(exclude_none=True) if hasattr(req, "model_dump") else req.dict(exclude_none=True)
    for key_field in ("anthropic_api_key", "openai_api_key", "gemini_api_key"):
        if key_field in updates:
            CONFIG[key_field] = updates.pop(key_field)
    CONFIG.update(updates)
    save_config(CONFIG)
    return {"status": "ok", "updated": list(updates.keys())}


# ── Providers ─────────────────────────────────────────────────────────────────


@app.get("/providers")
def list_providers():
    return {
        "providers": [
            {
                "id": "anthropic",
                "name": "Anthropic (Claude)",
                "available": True,
                "models": [
                    "claude-sonnet-4-20250514",
                    "claude-opus-4-20250514",
                    "claude-haiku-4-5-20251001",
                ],
            },
            {
                "id": "openai",
                "name": "OpenAI (GPT)",
                "available": OpenAIProvider is not None,
                "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
            },
            {
                "id": "gemini",
                "name": "Google (Gemini)",
                "available": GeminiProvider is not None,
                "models": [
                    "gemini-2.0-flash",
                    "gemini-1.5-pro",
                    "gemini-1.5-flash",
                ],
            },
        ]
    }


# ── Memory management ─────────────────────────────────────────────────────────


@app.delete("/memory/facts/{fact_id}")
def delete_fact(fact_id: int):
    try:
        with _db.lock, _db.conn:
            _db.conn.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
        return {"status": "deleted", "id": fact_id}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.delete("/memory/clear")
def clear_memory():
    try:
        with _db.lock, _db.conn:
            _db.conn.execute("DELETE FROM facts")
            _db.conn.execute("DELETE FROM notes")
        return {"status": "cleared"}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
