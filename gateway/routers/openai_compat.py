"""
OpenAI-compatible /v1/chat/completions endpoint.
Lets OpenWebUI talk to ControlPane using standard OpenAI API format.
"""
import json
import time
import uuid
import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/openai", tags=["openai-compat"])


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str  # maps to agent name
    messages: list[ChatMessage]
    stream: bool = False


def _completion_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex}"


@router.get("/v1/models")
def list_models(request: Request):
    loader = request.app.state.manifest_loader
    return {
        "object": "list",
        "data": [
            {
                "id": name,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "controlpane",
            }
            for name in loader.all()
        ],
    }


@router.post("/v1/chat/completions")
async def chat_completions(body: ChatRequest, request: Request):
    loader = request.app.state.manifest_loader
    manifest = loader.get(body.model)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Agent '{body.model}' not found")

    user_messages = [m for m in body.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user message provided")

    message = user_messages[-1].content
    thread_id = str(uuid.uuid4())
    mtime = loader.get_mtime(body.model)
    runtime = request.app.state.runtime_registry.get_or_build(manifest, mtime)

    if body.stream:
        return _stream_response(runtime, body.model, message, thread_id)

    try:
        result = runtime.invoke(message, thread_id)
    except Exception as e:
        logger.exception("OpenAI compat invoke failed")
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "id": _completion_id(),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result.output},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def _stream_response(runtime, model: str, message: str, thread_id: str) -> StreamingResponse:
    cid = _completion_id()
    created = int(time.time())

    async def event_generator():
        # Opening chunk — role
        yield _sse_chunk(cid, created, model, {"role": "assistant", "content": ""})
        try:
            async for chunk in runtime.stream(message, thread_id):
                if chunk.type == "token" and chunk.content:
                    yield _sse_chunk(cid, created, model, {"content": chunk.content})
                elif chunk.type == "done":
                    break
        except Exception as e:
            logger.exception("OpenAI compat stream error")
            yield _sse_chunk(cid, created, model, {"content": f"\n[error: {e}]"})

        # Closing chunk
        yield _sse_chunk(cid, created, model, {}, finish_reason="stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _sse_chunk(cid: str, created: int, model: str, delta: dict, finish_reason=None) -> str:
    payload = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(payload)}\n\n"
