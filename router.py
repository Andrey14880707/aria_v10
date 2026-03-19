# router.py — FastAPI REST backend for ARIA
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import CONFIG, MODEL, save_config
from db import MemoryDB
from state import AgentState
from tools import ToolRunner
from utils import append_log

# ---------------------------------------------------------------------------
# LLM provider routing
# ---------------------------------------------------------------------------

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


def _build_agent(provider: str, model: str):
    """Build agent with selected LLM provider."""
    from agent import Agent

    db = MemoryDB()
    state = AgentState()
    state.session_id = db.start_session()
    tools = ToolRunner(state, db)

    if provider == "anthropic" and AnthropicProvider:
        llm = AnthropicProvider(model=model)
    elif provider == "openai" and OpenAIProvider:
        llm = OpenAIProvider(model=model)
    elif provider == "gemini" and GeminiProvider:
        llm = GeminiProvider(model=model)
    else:
        # Fallback to default Anthropic client
        from llm import AnthropicClient
        llm = AnthropicClient(model=model)

    return Agent(llm, db, state, tools), db, state


# ---------------------------------------------------------------------------
# Singleton session (one active agent per server instance)
# ---------------------------------------------------------------------------

_db = MemoryDB()
_state = AgentState()
_state.session_id = _db.start_session()
_tools = ToolRunner(_state, _db)

try:
    from llm import AnthropicClient
    _llm = AnthropicClient()
except Exception:
    _llm = None

try:
    from agent import Agent
    _agent = Agent(_llm, _db, _state, _tools) if _llm else None
except Exception:
    _agent = None

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ARIA Backend",
    description="Local AI assistant REST API",
    version="10.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


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


class ToolRequest(BaseModel):
    tool: str
    args: Dict[str, Any] = {}


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LOG_FILE = Path.home() / ".aria_v9" / "aria.log"


def _get_agent_for_request(provider: str, model: str):
    """Return global agent if provider matches, else build ephemeral one."""
    global _agent, _llm, _db, _state, _tools

    current_provider = CONFIG.get("active_provider", "anthropic")
    if provider == current_provider and _agent is not None:
        return _agent, _db, _state

    # Build ephemeral agent with requested provider
    ag, db, st = _build_agent(provider, model)
    return ag, db, st


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health():
    return {"status": "ok", "version": "10.0.0"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(400, "Empty message")

    try:
        ag, db, st = _get_agent_for_request(req.provider, req.model)
        reply = ag.respond(req.message)
        append_log(f"[API] USER: {req.message[:200]}")
        append_log(f"[API] ARIA: {reply[:300]}")
        return ChatResponse(
            reply=reply,
            provider=req.provider,
            model=req.model,
            commands_run=st.commands_run,
            session_id=st.session_id,
        )
    except Exception as e:
        raise HTTPException(500, str(e))


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


@app.get("/logs", response_model=List[LogEntry])
def get_logs(lines: int = 100):
    if not LOG_FILE.exists():
        return []
    try:
        text = LOG_FILE.read_text(encoding="utf-8", errors="replace")
        all_lines = text.splitlines()
        return [LogEntry(line=l) for l in all_lines[-lines:]]
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/tools")
def list_tools():
    from safety import ALLOWED_TOOLS
    return {"tools": sorted(ALLOWED_TOOLS)}


@app.post("/tools/execute")
def execute_tool(req: ToolRequest):
    try:
        result = _tools.execute(req.tool, req.args)
        return {"result": result, "tool": req.tool}
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/settings")
def get_settings():
    safe = {k: v for k, v in CONFIG.items() if "key" not in k.lower()}
    safe["active_provider"] = CONFIG.get("active_provider", "anthropic")
    safe["active_model"] = CONFIG.get("active_model", MODEL)
    safe["anthropic_key_set"] = bool(os.environ.get("ANTHROPIC_API_KEY", CONFIG.get("anthropic_api_key", "")))
    safe["openai_key_set"] = bool(os.environ.get("OPENAI_API_KEY", CONFIG.get("openai_api_key", "")))
    safe["gemini_key_set"] = bool(os.environ.get("GEMINI_API_KEY", CONFIG.get("gemini_api_key", "")))
    return safe


@app.post("/settings")
def update_settings(req: SettingsRequest):
    updates = req.model_dump(exclude_none=True)

    # Handle API keys → store in config (for Termux usage)
    for key_field in ("anthropic_api_key", "openai_api_key", "gemini_api_key"):
        if key_field in updates:
            CONFIG[key_field] = updates.pop(key_field)

    CONFIG.update(updates)
    save_config(CONFIG)
    return {"status": "ok", "updated": list(updates.keys())}


@app.get("/providers")
def list_providers():
    return {
        "providers": [
            {
                "id": "anthropic",
                "name": "Anthropic (Claude)",
                "available": AnthropicProvider is not None or True,
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
                "models": [
                    "gpt-4o",
                    "gpt-4o-mini",
                    "gpt-4-turbo",
                ],
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
