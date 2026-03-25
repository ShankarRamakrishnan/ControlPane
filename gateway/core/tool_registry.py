import os
import sys
import logging
import importlib.util
from pathlib import Path
from langchain_core.tools import BaseTool
from gateway.models.manifest import AgentManifest

logger = logging.getLogger(__name__)

_tool_registry: dict[str, BaseTool] = {}
_tool_sources: dict[str, str] = {}


def register(t: BaseTool) -> BaseTool:
    """Register a LangChain tool by name. Use as a decorator on @tool functions."""
    _tool_registry[t.name] = t
    _tool_sources[t.name] = "python"
    logger.debug(f"Registered tool: {t.name}")
    return t


def register_many(tools: list[BaseTool], source: str) -> int:
    for t in tools:
        _tool_registry[t.name] = t
        _tool_sources[t.name] = source
    logger.info(f"Registered {len(tools)} tool(s) from source '{source}': {[t.name for t in tools]}")
    return len(tools)


def list_registered_with_sources() -> dict[str, str]:
    return dict(_tool_sources)


def get_tools_by_source_prefix(prefix: str) -> list[BaseTool]:
    return [_tool_registry[name] for name, src in _tool_sources.items() if src.startswith(prefix) and name in _tool_registry]


def load_tools_for_manifest(manifest: AgentManifest) -> list[BaseTool]:
    """Return list of tools for an agent based on its manifest tool definitions."""
    if not _tool_registry:
        logger.warning(
            "Tool registry is empty — discover_tools() has not been called yet. "
            "Ensure the app lifespan has run before resolving tools."
        )
    tools: list[BaseTool] = []
    for tool_def in manifest.tools:
        if tool_def.name in _tool_registry:
            tools.append(_tool_registry[tool_def.name])
        else:
            logger.warning(
                f"Tool '{tool_def.name}' requested by '{manifest.name}' not in registry. "
                f"Available: {list(_tool_registry.keys())}"
            )
    return tools


def list_registered() -> list[str]:
    return list(_tool_registry.keys())


def discover_tools(tools_dir: str | Path) -> int:
    """
    Scan a directory for *.py tool modules and import each one.
    Any module that calls register() at import time will add its tools.
    Returns the number of tools registered (not modules imported).
    """
    tools_path = Path(tools_dir)
    if not tools_path.exists():
        logger.warning(f"Tools directory not found: {tools_path}")
        return 0

    before = set(_tool_registry.keys())
    for py_file in sorted(tools_path.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        module_name = f"tools.{py_file.stem}"
        if module_name in sys.modules:
            continue
        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            logger.info(f"Loaded tool module: {py_file.name}")
        except Exception as e:
            logger.error(f"Failed to load tool module {py_file}: {e}")

    new_tools = [name for name in _tool_registry if name not in before]
    logger.info(f"Registered {len(new_tools)} tool(s): {new_tools}")
    return len(new_tools)
