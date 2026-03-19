# plugins/loader.py
"""
Plugin discovery and loading.

A plugin is any .py file in the plugins/ directory that contains a class
named Plugin with the following structure:

    class Plugin:
        name        = "plugin_name"      # unique identifier
        description = "what it does"     # shown in /плагины
        tools       = ["tool_one", ...]  # tool names it provides

        def tool_tool_one(self, args: dict) -> str:
            ...

The loader imports each file, finds the Plugin class, instantiates it,
and validates that every name in tools has a matching tool_<name> method.

Errors in individual plugin files are caught and reported as warnings —
they never crash the main process.
"""

import importlib.util
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class PluginError(Exception):
    pass


@dataclass
class PluginMeta:
    name: str
    description: str
    tools: List[str]
    instance: Any
    path: Path
    tool_fns: Dict[str, Callable] = field(default_factory=dict)


def _load_one(path: Path) -> Optional[PluginMeta]:
    """
    Load a single plugin file. Returns PluginMeta or None if the file
    has no Plugin class (that's fine — skip silently).
    Raises PluginError for invalid plugins that do declare a Plugin class.
    """
    spec = importlib.util.spec_from_file_location(f"plugin_{path.stem}", path)
    if spec is None or spec.loader is None:
        return None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    cls = getattr(module, "Plugin", None)
    if cls is None or not inspect.isclass(cls):
        return None  # not a plugin file — skip

    instance = cls()
    name        = str(getattr(cls, "name",        path.stem))
    description = str(getattr(cls, "description", ""))
    tools       = list(getattr(cls, "tools",      []))

    # Validate: every name in tools must have method tool_<name>
    tool_fns: Dict[str, Callable] = {}
    for tool_name in tools:
        method_name = f"tool_{tool_name}"
        fn = getattr(instance, method_name, None)
        if not callable(fn):
            raise PluginError(
                f"Plugin '{name}' lists tool '{tool_name}' "
                f"but has no method '{method_name}'"
            )
        tool_fns[tool_name] = fn

    return PluginMeta(
        name=name,
        description=description,
        tools=tools,
        instance=instance,
        path=path,
        tool_fns=tool_fns,
    )


def load_plugins(plugin_dir: Path) -> List[PluginMeta]:
    """
    Scan plugin_dir for *.py files, load each one.
    Skips files starting with _ (e.g. __init__.py, _internal.py).
    Catches all errors per-file and prints a warning — never crashes.
    Returns list of successfully loaded PluginMeta objects.
    """
    plugin_dir = Path(plugin_dir).resolve()
    if not plugin_dir.exists():
        return []

    results: List[PluginMeta] = []

    for path in sorted(plugin_dir.glob("*.py")):
        if path.stem.startswith("_"):
            continue  # skip __init__, _loader, etc.
        if path.name == "loader.py":
            continue  # skip ourselves

        try:
            meta = _load_one(path)
            if meta is not None:
                results.append(meta)
        except PluginError as e:
            print(f"[plugins] Warning: {path.name}: {e}")
        except Exception as e:
            print(f"[plugins] Warning: failed to load {path.name}: {e}")

    return results
