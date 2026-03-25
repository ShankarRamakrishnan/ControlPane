import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from gateway.adapters.webhook import WebhookAdapter
    from gateway.core.capability_registry import CapabilityRegistry
    from gateway.core.execution_engine import ExecutionEngine
    from gateway.core.manifest_loader import ManifestLoader
    from gateway.core.runtime import RuntimeRegistry
    from gateway.core.scheduler import TriggerScheduler
    from gateway.core.tool_registry import discover_tools

    tools_dir = os.getenv("TOOLS_DIR", "/app/tools")
    discover_tools(tools_dir)

    manifests_dir = os.getenv("MANIFESTS_DIR", "/app/manifests")
    loader = ManifestLoader(manifests_dir)
    loader.load_all()

    from gateway.core.platform_loader import initialize as init_platform_engine
    from providers.registry import default_registry as provider_plugin_registry
    platform_yaml = Path(manifests_dir) / "platform.yaml"
    if platform_yaml.exists():
        init_platform_engine(str(platform_yaml), plugin_registry=provider_plugin_registry)
        logger.info("Platform engine initialized")

    from gateway.adapters import mcp_tool_adapter, openapi_tool_adapter
    from gateway.core.tool_registry import register_many
    from gateway.core.platform_loader import get_engine as get_platform_engine

    _platform = get_platform_engine()
    if _platform:
        for _provider in _platform._manifest.providers:
            if _provider.status == "stub":
                continue
            try:
                if _provider.kind == "mcp":
                    _mcp_tools = mcp_tool_adapter.discover_tools(_provider)
                    register_many(_mcp_tools, source=f"mcp:{_provider.name}")
                elif _provider.kind == "api" and _provider.transport.spec_url:
                    _api_tools = openapi_tool_adapter.discover_tools(_provider)
                    register_many(_api_tools, source=f"openapi:{_provider.name}")
            except Exception as _e:
                logger.warning("Tool discovery failed for provider '%s': %s", _provider.name, _e)

    capability_registry = CapabilityRegistry()
    capability_registry.register("webhook", WebhookAdapter())

    registry = RuntimeRegistry()
    engine = ExecutionEngine(loader, registry, capability_registry)

    scheduler = TriggerScheduler()
    scheduler.set_engine(engine)
    scheduler.register_all(loader.all())
    scheduler.start()

    app.state.manifest_loader = loader
    app.state.runtime_registry = registry
    app.state.capability_registry = capability_registry
    app.state.execution_engine = engine
    app.state.scheduler = scheduler

    logger.info(f"ControlPane gateway started — {len(loader.all())} agent(s) loaded")
    yield

    scheduler.shutdown()
    logger.info("ControlPane gateway shutting down")


app = FastAPI(
    title="ControlPane Gateway",
    description="Agent Control Plane — unified gateway for LangGraph agents",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from gateway.routers import health, agents, manifests, openai_compat, triggers

app.include_router(health.router)
app.include_router(agents.router)
app.include_router(manifests.router)
app.include_router(openai_compat.router)
app.include_router(triggers.router)


@app.get("/")
def root():
    return {
        "name": "ControlPane",
        "version": "0.1.0",
        "docs": "/docs",
        "agents": "/agents",
        "manifests": "/manifests",
        "webhooks": "/webhooks/{agent}/{trigger_id}",
    }
