import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

_langsmith_enabled = False

try:
    if os.getenv("LANGCHAIN_API_KEY") and os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true":
        from langsmith import Client
        _client = Client()
        _langsmith_enabled = True
        logger.info("LangSmith tracing enabled")
except Exception as e:
    logger.warning(f"LangSmith not available: {e}")
    _client = None


def is_tracing_enabled() -> bool:
    return _langsmith_enabled


def get_trace_url(run_id: str) -> str | None:
    """Return the LangSmith trace URL for a given run ID."""
    if not _langsmith_enabled or not _client:
        return None
    try:
        project = os.getenv("LANGCHAIN_PROJECT", "controlpane")
        return f"https://smith.langchain.com/o/default/projects/p/{project}/r/{run_id}"
    except Exception:
        return None


def setup_project_tracing(agent_name: str) -> dict[str, Any]:
    """Return LangChain config dict for tracing a specific agent run."""
    project = os.getenv("LANGCHAIN_PROJECT", "controlpane")
    return {
        "tags": [agent_name, "controlpane"],
        "metadata": {"agent": agent_name, "project": project},
    }
