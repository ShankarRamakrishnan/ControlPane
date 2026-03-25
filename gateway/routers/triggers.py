"""
Webhook trigger ingress.

POST /webhooks/{agent_name}/{trigger_id}

Validates the request (HMAC signature, event filter), renders the input
from the manifest template, then hands off to the ExecutionEngine.
"""
import hashlib
import hmac
import json
import logging
import os
import uuid

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from gateway.models.invocation import (
    InvocationContext,
    InvocationSource,
    UnifiedInvocationRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _verify_hmac(body: bytes, secret: str, signature: str | None) -> bool:
    """Validate GitHub-style 'sha256=<hex>' or bare hex signatures."""
    if not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    candidate = signature.removeprefix("sha256=")
    return hmac.compare_digest(expected, candidate)


def _matches_filter(payload: dict, event_filter: dict | None) -> bool:
    """Return True if all key=value pairs in event_filter match the payload."""
    if not event_filter:
        return True
    return all(payload.get(k) == v for k, v in event_filter.items())


def _render_input(template: str, payload: dict) -> str:
    """Render a Jinja2 input_template with the webhook payload."""
    try:
        from jinja2 import Template
        return Template(template).render(payload=payload)
    except Exception as exc:
        logger.warning(f"Template render failed ({exc}), using raw template")
        return template


@router.post("/{agent_name}/{trigger_id}")
async def webhook_trigger(
    agent_name: str,
    trigger_id: str,
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_webhook_signature: str | None = Header(default=None),
):
    loader = request.app.state.manifest_loader
    manifest = loader.get(agent_name)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    trigger = next(
        (t for t in manifest.triggers if t.id == trigger_id and t.type == "webhook"),
        None,
    )
    if not trigger:
        raise HTTPException(
            status_code=404,
            detail=f"Webhook trigger '{trigger_id}' not found on agent '{agent_name}'",
        )

    if not trigger.enabled:
        raise HTTPException(status_code=409, detail=f"Trigger '{trigger_id}' is disabled")

    # HMAC verification
    if trigger.secret_env:
        secret = os.getenv(trigger.secret_env)
        if not secret:
            raise HTTPException(
                status_code=500,
                detail=f"Secret env var '{trigger.secret_env}' is not set",
            )
        body = await request.body()
        sig = x_hub_signature_256 or x_webhook_signature
        if not _verify_hmac(body, secret, sig):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Parse payload
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    # Event filter
    if not _matches_filter(payload, trigger.event_filter):
        return JSONResponse({"status": "filtered", "trigger_id": trigger_id})

    # Build input text
    if trigger.input_template:
        input_text = _render_input(trigger.input_template, payload)
    elif trigger.input:
        input_text = trigger.input
    else:
        input_text = json.dumps(payload)

    thread_id = trigger.thread_id or str(uuid.uuid4())

    engine = request.app.state.execution_engine
    req = UnifiedInvocationRequest(
        agent=agent_name,
        source=InvocationSource.webhook,
        thread_id=thread_id,
        input=input_text,
        context=InvocationContext(trigger_id=trigger_id, event_payload=payload),
    )

    try:
        result = await engine.execute(req)
    except Exception as exc:
        logger.exception(f"Webhook trigger '{trigger_id}' on '{agent_name}' failed")
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "status": "ok",
        "agent": agent_name,
        "trigger_id": trigger_id,
        "thread_id": result.thread_id,
        "latency_ms": result.latency_ms,
    }
