import json
import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from gateway.models.invocation import (
    InvocationContext,
    InvocationSource,
    UnifiedInvocationRequest,
)
from gateway.models.runtime import InvokeRequest, InvokeResponse, AgentSummary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents"])


def _get_runtime(agent_name: str, request: Request):
    loader = request.app.state.manifest_loader
    manifest = loader.get(agent_name)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    mtime = loader.get_mtime(agent_name)
    runtime = request.app.state.runtime_registry.get_or_build(manifest, mtime)
    return runtime


@router.get("", response_model=list[AgentSummary])
def list_agents(request: Request):
    loader = request.app.state.manifest_loader
    return [
        AgentSummary(
            name=m.name,
            version=m.version,
            description=m.description,
            model=f"{m.model.provider}/{m.model.name}",
            tools=[t.name for t in m.tools],
        )
        for m in loader.all().values()
    ]


@router.post("/{agent_name}/invoke", response_model=InvokeResponse)
async def invoke_agent(agent_name: str, body: InvokeRequest, request: Request):
    engine = request.app.state.execution_engine
    req = UnifiedInvocationRequest(
        agent=agent_name,
        source=InvocationSource.manual,
        thread_id=body.thread_id,
        input=body.message,
        context=InvocationContext(),
        metadata=body.metadata,
    )
    try:
        return await engine.execute(req)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Agent '{agent_name}' invocation failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{agent_name}/stream")
async def stream_agent(agent_name: str, body: InvokeRequest, request: Request):
    runtime = _get_runtime(agent_name, request)

    async def event_generator():
        try:
            async for chunk in runtime.stream(body.message, body.thread_id):
                yield f"data: {chunk.model_dump_json()}\n\n"
        except Exception as e:
            logger.exception(f"Stream error for agent '{agent_name}'")
            error_chunk = json.dumps({"type": "error", "content": str(e), "metadata": {}})
            yield f"data: {error_chunk}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
