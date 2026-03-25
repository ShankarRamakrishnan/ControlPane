import os
import logging
from contextlib import asynccontextmanager
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
