import logging
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from gateway.models.manifest import AgentManifest, TriggerDef

logger = logging.getLogger(__name__)


class TriggerScheduler:
    """
    Wraps APScheduler. Reads schedule triggers from manifests and registers
    cron jobs that flow through the ExecutionEngine.

    Engine is injected after construction (set_engine) to avoid circular imports
    at startup.
    """

    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._engine = None

    def set_engine(self, engine) -> None:
        self._engine = engine

    def start(self) -> None:
        self._scheduler.start()
        logger.info("Trigger scheduler started")

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def register_all(self, manifests: dict[str, AgentManifest]) -> None:
        for manifest in manifests.values():
            self.register_manifest(manifest)

    def register_manifest(self, manifest: AgentManifest) -> None:
        self._remove_manifest_jobs(manifest.name)
        for trigger in manifest.triggers:
            if trigger.type == "schedule" and trigger.enabled:
                self._register_schedule(manifest.name, trigger)

    def _remove_manifest_jobs(self, agent_name: str) -> None:
        for job in self._scheduler.get_jobs():
            if job.id.startswith(f"agent:{agent_name}:"):
                job.remove()
                logger.debug(f"Removed job {job.id}")

    def _register_schedule(self, agent_name: str, trigger: TriggerDef) -> None:
        if not trigger.cron:
            logger.warning(f"Schedule trigger '{trigger.id}' on '{agent_name}' has no cron expression — skipped")
            return

        job_id = f"agent:{agent_name}:{trigger.id}"

        async def run_trigger():
            if not self._engine:
                logger.error("ExecutionEngine not set on scheduler — cannot run trigger")
                return

            from gateway.models.invocation import (
                InvocationContext,
                InvocationSource,
                UnifiedInvocationRequest,
            )

            thread_id = trigger.thread_id or str(uuid.uuid4())
            req = UnifiedInvocationRequest(
                agent=agent_name,
                source=InvocationSource.schedule,
                thread_id=thread_id,
                input=trigger.input or "",
                context=InvocationContext(trigger_id=trigger.id),
            )
            try:
                await self._engine.execute(req)
            except Exception as e:
                logger.error(f"Schedule trigger '{trigger.id}' on '{agent_name}' failed: {e}")

        self._scheduler.add_job(
            run_trigger,
            trigger=CronTrigger.from_crontab(trigger.cron, timezone=trigger.timezone),
            id=job_id,
            name=f"{agent_name}/{trigger.id}",
            replace_existing=True,
        )
        logger.info(
            f"Registered schedule trigger '{trigger.id}' on '{agent_name}': "
            f"cron='{trigger.cron}' tz='{trigger.timezone}'"
        )
