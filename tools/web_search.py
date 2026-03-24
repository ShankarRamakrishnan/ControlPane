import os
import httpx
from langchain_core.tools import tool
from gateway.core.tool_registry import register


@register
@tool
def web_search(query: str) -> str:
    """Search the web for current information. Input: a search query string."""
    # Uses Tavily if TAVILY_API_KEY is set, otherwise falls back to DuckDuckGo
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        return _tavily_search(query, tavily_key)
    return _duckduckgo_search(query)


def _tavily_search(query: str, api_key: str) -> str:
    try:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": query, "max_results": 5},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return "No results found."
        lines = []
        for r in results[:3]:
            lines.append(f"- {r.get('title', '')}: {r.get('url', '')}\n  {r.get('content', '')[:200]}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Search error: {e}"


def _duckduckgo_search(query: str) -> str:
    try:
        resp = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        abstract = data.get("AbstractText", "")
        if abstract:
            return abstract
        related = data.get("RelatedTopics", [])
        lines = []
        for r in related[:3]:
            if isinstance(r, dict) and "Text" in r:
                lines.append(f"- {r['Text']}")
        return "\n".join(lines) if lines else "No results found."
    except Exception as e:
        return f"Search error: {e}"
