import logging
import time
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from gateway.models.manifest import AgentManifest
from gateway.models.runtime import InvokeResponse, ToolCallRecord
from gateway.core.tool_registry import load_tools_for_manifest
from gateway.core.observability import get_trace_url, setup_project_tracing

logger = logging.getLogger(__name__)


def _build_llm(manifest: AgentManifest):
    """Instantiate the LLM based on manifest model config."""
    cfg = manifest.model
    if cfg.provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=cfg.name,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )
    elif cfg.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=cfg.name,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens or 4096,
        )
    else:
        raise ValueError(f"Unsupported model provider: {cfg.provider}")


class AgentRuntime:
    """
    Wraps a LangGraph ReAct agent compiled from an AgentManifest.
    One instance per manifest; thread_id controls conversation memory.
    """

    def __init__(self, manifest: AgentManifest):
        self.manifest = manifest
        self._checkpointer = MemorySaver()
        self._graph = self._compile()

    def _compile(self):
        llm = _build_llm(self.manifest)
        tools = load_tools_for_manifest(self.manifest)

        graph = create_react_agent(
            model=llm,
            tools=tools,
            checkpointer=self._checkpointer,
        )
        logger.info(
            f"Compiled agent '{self.manifest.name}' with {len(tools)} tool(s): "
            f"{[t.name for t in tools]}"
        )
        return graph

    def invoke(self, message: str, thread_id: str, metadata: dict[str, Any] | None = None) -> InvokeResponse:
        import os
        start = time.time()

        config: dict[str, Any] = {
            "configurable": {"thread_id": thread_id},
            **setup_project_tracing(self.manifest.name),
        }
        if metadata:
            config.setdefault("metadata", {}).update(metadata)

        # Attach a tracer to capture the run_id for the trace URL
        tracer = None
        if os.getenv("LANGCHAIN_API_KEY") and os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true":
            try:
                from langchain.callbacks.tracers import LangChainTracer
                tracer = LangChainTracer(
                    project_name=os.getenv("LANGCHAIN_PROJECT", "controlpane")
                )
                config["callbacks"] = [tracer]
            except Exception:
                pass

        messages = []
        if self.manifest.prompts.system:
            messages.append(SystemMessage(content=self.manifest.prompts.system))
        messages.append(HumanMessage(content=message))

        result = self._graph.invoke({"messages": messages}, config=config)

        latency_ms = (time.time() - start) * 1000

        # Extract final AI message
        ai_messages = [m for m in result["messages"] if m.__class__.__name__ == "AIMessage"]
        output = ai_messages[-1].content if ai_messages else ""

        # Extract tool calls from the message history
        tool_calls: list[ToolCallRecord] = []
        for msg in result["messages"]:
            if msg.__class__.__name__ == "ToolMessage":
                tool_calls.append(
                    ToolCallRecord(
                        tool=msg.name,
                        input={},
                        output=str(msg.content),
                        duration_ms=0,
                    )
                )

        # Resolve trace URL from captured run_id
        trace_url: str | None = None
        if tracer is not None and hasattr(tracer, "latest_run") and tracer.latest_run:
            trace_url = get_trace_url(str(tracer.latest_run.id))

        return InvokeResponse(
            thread_id=thread_id,
            output=output,
            tool_calls=tool_calls,
            trace_url=trace_url,
            latency_ms=round(latency_ms, 2),
        )

    async def stream(self, message: str, thread_id: str):
        """Yield StreamChunk dicts for SSE streaming."""
        from gateway.models.runtime import StreamChunk

        config = {
            "configurable": {"thread_id": thread_id},
            **setup_project_tracing(self.manifest.name),
        }

        messages = []
        if self.manifest.prompts.system:
            messages.append(SystemMessage(content=self.manifest.prompts.system))
        messages.append(HumanMessage(content=message))

        async for event in self._graph.astream_events(
            {"messages": messages}, config=config, version="v2"
        ):
            kind = event.get("event")
            if kind == "on_chat_model_stream":
                chunk = event["data"].get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield StreamChunk(type="token", content=chunk.content)
            elif kind == "on_tool_start":
                yield StreamChunk(type="tool_call", content=event["name"], metadata=event.get("data", {}))
            elif kind == "on_tool_end":
                output = event["data"].get("output", "")
                yield StreamChunk(type="tool_result", content=str(output))

        yield StreamChunk(type="done", content="")


class RuntimeRegistry:
    """Manages compiled AgentRuntime instances, one per manifest+mtime."""

    def __init__(self):
        self._runtimes: dict[str, AgentRuntime] = {}

    def get_or_build(self, manifest: AgentManifest, mtime: float = 0.0) -> AgentRuntime:
        # Include mtime so a changed manifest (even at same version) triggers recompile.
        key = f"{manifest.name}:{manifest.version}:{mtime}"
        if key not in self._runtimes:
            self._invalidate_name(manifest.name)
            self._runtimes[key] = AgentRuntime(manifest)
        return self._runtimes[key]

    def _invalidate_name(self, name: str) -> None:
        stale = [k for k in self._runtimes if k.startswith(f"{name}:")]
        for k in stale:
            del self._runtimes[k]
