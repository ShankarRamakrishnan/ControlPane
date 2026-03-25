import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx
import yaml
from langchain_core.tools import StructuredTool
from pydantic import Field, create_model

from gateway.models.platform_manifest import ProviderDef

logger = logging.getLogger(__name__)


def discover_tools(provider: ProviderDef) -> list:
    spec_url = provider.transport.spec_url
    if not spec_url:
        raise ValueError(f"Provider '{provider.name}': transport.spec_url is required for OpenAPI discovery")
    spec = _load_spec(spec_url)
    base_url = provider.transport.base_url or _infer_base_url(spec)
    auth_headers = _build_headers(provider)
    return _extract_tools(spec, base_url, auth_headers)


def _load_spec(spec_url: str) -> dict:
    if spec_url.startswith("http://") or spec_url.startswith("https://"):
        resp = httpx.get(spec_url, timeout=10)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return yaml.safe_load(resp.text)
    else:
        p = Path(spec_url)
        text = p.read_text()
        if p.suffix == ".json":
            return json.loads(text)
        return yaml.safe_load(text)


def _infer_base_url(spec: dict) -> str:
    try:
        return spec["servers"][0]["url"]
    except (KeyError, IndexError, TypeError):
        pass
    try:
        return "https://" + spec["host"] + spec.get("basePath", "")
    except (KeyError, TypeError):
        pass
    return ""


def _build_headers(provider: ProviderDef) -> dict[str, str]:
    headers = {}
    if provider.auth:
        secret_val = os.getenv(provider.auth.secret, "") if provider.auth.secret else ""
        for k, v in provider.auth.headers.items():
            headers[k] = v.replace("{{secret}}", secret_val)
    return headers


def _extract_tools(spec: dict, base_url: str, auth_headers: dict) -> list:
    tools = []
    for path_template, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            if not isinstance(operation, dict) or not operation.get("operationId"):
                continue
            tool = _make_operation_tool(operation, method, path_template, base_url, auth_headers)
            if tool is not None:
                tools.append(tool)
    return tools


def _make_operation_tool(operation, method, path_template, base_url, auth_headers) -> StructuredTool | None:
    op_id = operation.get("operationId")
    if not op_id:
        return None

    summary = operation.get("summary", "")
    description = operation.get("description", summary)

    parameters = operation.get("parameters", [])
    parameters = [p for p in parameters if isinstance(p, dict) and "name" in p and "$ref" not in p]

    body_schema = {}
    rb = operation.get("requestBody", {})
    if rb:
        content = rb.get("content", {})
        for media_type in ("application/json", "application/x-www-form-urlencoded"):
            if media_type in content:
                body_schema = content[media_type].get("schema", {})
                if "$ref" in body_schema:
                    body_schema = {}
                break

    TYPE_MAP = {"string": str, "integer": int, "number": float, "boolean": bool, "array": list, "object": dict}

    fields = {}
    path_params: set[str] = set()
    query_params: set[str] = set()
    body_params: set[str] = set()

    for param in parameters:
        name = param["name"]
        location = param.get("in", "query")
        schema = param.get("schema", {})
        py_type = TYPE_MAP.get(schema.get("type", "string"), str)
        desc = param.get("description", schema.get("description", ""))
        if location == "path":
            path_params.add(name)
            fields[name] = (py_type, Field(..., description=desc))
        elif location == "query":
            if param.get("required"):
                query_params.add(name)
                fields[name] = (py_type, Field(..., description=desc))
            else:
                query_params.add(name)
                fields[name] = (py_type | None, Field(default=None, description=desc))

    body_required = set(body_schema.get("required", []))
    for name, prop_schema in body_schema.get("properties", {}).items():
        py_type = TYPE_MAP.get(prop_schema.get("type", "string"), str)
        desc = prop_schema.get("description", "")
        body_params.add(name)
        if name in body_required:
            fields[name] = (py_type, Field(..., description=desc))
        else:
            fields[name] = (py_type | None, Field(default=None, description=desc))

    args_model = create_model(f"{op_id}Args", **fields) if fields else None

    def run(**kwargs) -> str:
        url = base_url + path_template
        for p in path_params:
            url = url.replace(f"{{{p}}}", str(kwargs.pop(p, "")))
        qp = {k: v for k in query_params if (v := kwargs.get(k)) is not None}
        body = {k: v for k in body_params if (v := kwargs.get(k)) is not None}
        resp = httpx.request(
            method.upper(),
            url,
            params=qp or None,
            json=body or None,
            headers=auth_headers,
            timeout=15,
        )
        resp.raise_for_status()
        try:
            return json.dumps(resp.json())
        except Exception:
            return resp.text

    return StructuredTool.from_function(func=run, name=op_id, description=description, args_schema=args_model)
