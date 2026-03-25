from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SchemaPropertyDef(BaseModel):
    type: str
    description: str | None = None
    enum: list[str] | None = None


class SchemaDef(BaseModel):
    type: str = "object"
    properties: dict[str, SchemaPropertyDef] = {}


class CapabilityDef(BaseModel):
    name: str
    description: str = ""
    input_schema: str
    output_schema: str
    tags: list[str] = []


class TransportConfig(BaseModel):
    type: Literal["http", "stdio", "http_mcp"]
    base_url: str | None = None
    command: list[str] | None = None
    spec_url: str | None = None


class AuthConfig(BaseModel):
    type: str = "none"
    secret: str | None = None
    headers: dict[str, str] = {}


class ProviderDef(BaseModel):
    name: str
    kind: Literal["api", "mcp"]
    transport: TransportConfig
    auth: AuthConfig | None = None
    supports: list[str] = []
    status: str = "active"


class BindingDef(BaseModel):
    capability: str
    provider: str
    operation: str
    method: str = "GET"
    input_map: dict[str, str] = {}
    value_maps: dict[str, dict[str, str]] = {}
    results_key: str = ""
    output_map: dict[str, str] = {}
    url_prefixes: dict[str, str] = {}


class RoutingPolicy(BaseModel):
    strategy: Literal["fallback", "merge", "quorum"] = "fallback"
    order: list[str] = []


class PoliciesConfig(BaseModel):
    routing: dict[str, RoutingPolicy] = {}


class AgentPermissions(BaseModel):
    name: str
    allowed_capabilities: list[str] = []


class PlatformManifest(BaseModel):
    kind: str = "platform"
    version: str = "1.0.0"
    schemas: dict[str, SchemaDef] = {}
    capabilities: list[CapabilityDef] = []
    providers: list[ProviderDef] = []
    bindings: list[BindingDef] = []
    policies: PoliciesConfig = Field(default_factory=PoliciesConfig)
    agents: list[AgentPermissions] = []
