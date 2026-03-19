# safety.py — Tool allowlist and path safety for ARIA
from pathlib import Path


class ToolPolicyError(Exception):
    pass


# Shell tools (handled by tools_shell.py with its own stricter validation)
SHELL_TOOLS = {
    "run_shell",
    "read_file",
    "write_file",
    "list_dir",
    "git_status",
    "git_add",
    "git_commit",
    "git_push",
}

# Agent (Termux API) tools
ALLOWED_TOOLS = {
    "battery_status",
    "location",
    "camera_photo",
    "speak",
    "notification",
    "torch",
    "weather",
    "internet_search",
    "read_notes",
    "append_note",
    "system_info",
    "list_dir",
    "read_file",
    "list_packages",
    "open_app",
    "open_url",
    "tap",
    "swipe",
    "input_text",
    "keyevent",
    "screenshot",
    "get_screen_size",
    "get_current_app",
    "open_settings",
    "clipboard_get",
    "clipboard_set",
    "share",
    "vibrate",
    "volume",
    "wifi_info",
    "telephony_info",
    "download_file",
    "http_get",
    "run_termux_intent",
    "sleep",
    "echo",
    "read_webpage",
    "listen",
    "recall_memory",
}


BLOCKED_PATHS = {
    "/system",
    "/vendor",
    "/proc",
    "/dev",
    "/sys",
}


class SafetyPolicy:

    @staticmethod
    def ensure_tool_allowed(tool_name: str) -> None:
        if tool_name not in ALLOWED_TOOLS:
            raise ToolPolicyError(f"tool_not_allowed:{tool_name}")

    @staticmethod
    def ensure_safe_path(path: str) -> Path:
        p = Path(path).expanduser().resolve()
        for blocked in BLOCKED_PATHS:
            if str(p).startswith(blocked):
                raise ToolPolicyError(f"path_blocked:{p}")
        return p

    @staticmethod
    def ensure_shell_tool_allowed(tool_name: str) -> None:
        if tool_name not in SHELL_TOOLS:
            raise ToolPolicyError(f"shell_tool_not_allowed:{tool_name}")
