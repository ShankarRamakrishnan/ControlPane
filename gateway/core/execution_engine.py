import asyncio
import logging
from typing import Any

from gateway.models.invocation import UnifiedInvocationRequest
from gateway.models.runtime import InvokeResponse

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    Single execution path for all invocation sources: manual, schedule, webhook.

    All triggers normalize into a UnifiedInvocationRequest, flow through here,
    and optionally deliver results to configured outputs via the CapabilityRegistry.
    """

    def __init__(self, manifest_loader, runtime_registry, capability_registry):
        self.manifest_loader = manifest_loader
        self.runtime_registry = runtime_registry
        self.capability_registry = capability_registry

    async def execute(self, request: UnifiedInvocationRequest) -> InvokeResponse:
        manifest = self.manifest_loader.get(request.agent)
        if not manifest:
            raise ValueError(f"Agent '{request.agent}' not found")

        mtime = self.manifest_loader.get_mtime(request.agent)
        runtime = self.runtime_registry.get_or_build(manifest, mtime)

        metadata: dict[str, Any] = {
            "source": request.source.value,
            **request.metadata,
        }
        if request.context.trigger_id:
            metadata["trigger_id"] = request.context.trigger_id

        # runtime.invoke is synchronous — run in thread pool to avoid blocking the event loop
        result = await asyncio.to_thread(
            runtime.invoke, request.input, request.thread_id, metadata
        )

        logger.info(
            f"[{request.source.value}] agent='{request.agent}' "
            f"trigger='{request.context.trigger_id}' "
            f"thread='{request.thread_id}' latency={result.latency_ms}ms"
        )

        await self._route_outputs(manifest, result, request)

        return result

    async def _route_outputs(self, manifest, result: InvokeResponse, request: UnifiedInvocationRequest) -> None:
        for output in manifest.outputs:
            provider = manifest.providers.get(output.provider)
            if not provider:
                logger.warning(
                    f"Output '{output.name}' references unknown provider '{output.provider}' — skipped"
                )
                continue

            payload = {
                "agent": manifest.name,
                "source": request.source.value,
                "trigger_id": request.context.trigger_id,
                "thread_id": result.thread_id,
                "output": result.output,
                "latency_ms": result.latency_ms,
            }
            try:
                await self.capability_registry.deliver(provider, payload, output.name)
            except Exception as e:
                logger.warning(f"Output '{output.name}' delivery failed: {e}")
