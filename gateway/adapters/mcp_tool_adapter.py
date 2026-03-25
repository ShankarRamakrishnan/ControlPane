import asyncio
import json
import logging
import os
import threading
from typing import Any

import httpx
from langchain_core.tools import StructuredTool
from pydantic import Field, create_model

from gateway.models.platform_manifest import ProviderDef

logger = logging.getLogger(__name__)


def discover_tools(provider: ProviderDef) -> list:
    if provider.transport.type == "stdio":
        return _discover_stdio(provider)
    elif provider.transport.type in ("http", "http_mcp"):
        return _discover_http(provider)
    raise ValueError(f"Unsupported MCP transport '{provider.transport.type}' for provider '{provider.name}'")


def _schema_to_model(tool_name: str, schema: dict):
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    if not props:
        return None
    TYPE_MAP = {"string": str, "integer": int, "number": float, "boolean": bool, "array": list, "object": dict}
    fields = {}
    for name, prop_schema in props.items():
        py_type = TYPE_MAP.get(prop_schema.get("type", "string"), str)
        desc = prop_schema.get("description", "")
        if name in required:
            fields[name] = (py_type, Field(..., description=desc))
        else:
            fields[name] = (py_type | None, Field(default=None, description=desc))
    return create_model(f"{tool_name}Args", **fields)


def _build_headers(provider: ProviderDef) -> dict[str, str]:
    headers = {}
    if provider.auth:
        secret_val = os.getenv(provider.auth.secret, "") if provider.auth.secret else ""
        for k, v in provider.auth.headers.items():
            headers[k] = v.replace("{{secret}}", secret_val)
    return headers


def _discover_http(provider: ProviderDef) -> list:
    base_url = provider.transport.base_url.rstrip("/")
    headers = _build_headers(provider)

    resp = httpx.post(
        base_url,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    tools_data = resp.json()["result"]["tools"]

    return [_make_http_tool(td, base_url, headers) for td in tools_data]


def _make_http_tool(td: dict, base_url: str, headers: dict) -> StructuredTool:
    name = td["name"]
    description = td.get("description", "")
    args_model = _schema_to_model(name, td.get("inputSchema", {}))

    def run(**kwargs) -> str:
        r = httpx.post(
            base_url,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": name, "arguments": kwargs}},
            headers=headers,
            timeout=30,
        )
        r.raise_for_status()
        content = r.json().get("result", {}).get("content", [])
        return "\n".join(c.get("text", "") for c in content if c.get("type") == "text")

    return StructuredTool.from_function(func=run, name=name, description=description, args_schema=args_model)


class StdioMCPConnection:
    def __init__(self, command: list[str]):
        self._command = command
        self._ready = threading.Event()
        self._session = None
        self._shutdown = None
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        asyncio.run_coroutine_threadsafe(self._run(), self._loop)
        if not self._ready.wait(timeout=30):
            raise RuntimeError(f"Timed out waiting for stdio MCP connection: {self._command}")

    async def _run(self):
        try:
            from mcp.client.stdio import stdio_client, StdioServerParameters
            from mcp import ClientSession
        except ImportError:
            raise ImportError("mcp package required for stdio transport: pip install mcp")
        self._shutdown = asyncio.Event()
        params = StdioServerParameters(command=self._command[0], args=self._command[1:])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self._session = session
                self._ready.set()
                await self._shutdown.wait()

    def list_tools(self) -> list:
        return asyncio.run_coroutine_threadsafe(self._session.list_tools(), self._loop).result(timeout=10).tools

    def call_tool(self, name: str, arguments: dict) -> str:
        result = asyncio.run_coroutine_threadsafe(
            self._session.call_tool(name, arguments), self._loop
        ).result(timeout=30)
        return "\n".join(item.text for item in result.content if hasattr(item, "text"))

    def close(self):
        self._loop.call_soon_threadsafe(self._shutdown.set)


def _discover_stdio(provider: ProviderDef) -> list:
    cmd = provider.transport.command
    if not cmd:
        raise ValueError(f"Provider '{provider.name}': stdio transport requires 'command'")
    conn = StdioMCPConnection(cmd)
    return [_make_stdio_tool(td, conn) for td in conn.list_tools()]


def _make_stdio_tool(td, conn: StdioMCPConnection) -> StructuredTool:
    name = td.name
    description = td.description or ""
    schema = td.inputSchema if hasattr(td, "inputSchema") else {}
    if hasattr(schema, "model_dump"):
        schema = schema.model_dump()
    args_model = _schema_to_model(name, schema)

    def run(**kwargs) -> str:
        return conn.call_tool(name, kwargs)

    return StructuredTool.from_function(func=run, name=name, description=description, args_schema=args_model)
