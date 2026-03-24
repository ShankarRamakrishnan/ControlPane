# ControlPane

> The Agent Control Plane — one gateway, one manifest, one runtime for your LangGraph agents.

---

## The Problem

LangChain, LangGraph, LangSmith, and Langflow are four genuinely powerful tools. But they are not a platform — they are an ecosystem. Teams using them today face:

- No unified project model (what *is* an agent, exactly?)
- No single runtime contract (input schema, output schema, state schema)
- Authoring, execution, debugging, and deployment are separate experiences
- Every team rolls its own glue code — and it's never the same glue

ControlPane is the thin control plane that sits on top and fixes this without replacing anything.

---

## What ControlPane Is

A FastAPI gateway that:
1. Reads agent definitions from **YAML manifests**
2. Compiles them into **LangGraph agents** at runtime
3. Exposes a clean **REST + SSE API** (and an OpenAI-compatible API for OpenWebUI)
4. Routes all traces to **LangSmith** automatically

You define an agent once in YAML. ControlPane handles the rest.

---

## Architecture

```
┌─────────────────────────────────────┐
│           OpenWebUI  (port 3000)    │  ← human interface
└───────────────────┬─────────────────┘
                    │ OpenAI-compat API
┌───────────────────▼─────────────────┐
│       ControlPane Gateway           │  ← this project
│       FastAPI  (port 8000)          │
│                                     │
│  ┌──────────────────────────────┐   │
│  │  Manifest Loader             │   │  reads /manifests/*.yaml
│  │  Tool Registry               │   │  auto-discovers /tools/*.py
│  │  Runtime Registry            │   │  one LangGraph per manifest
│  └──────────────────────────────┘   │
└───────────────────┬─────────────────┘
                    │
┌───────────────────▼─────────────────┐
│        LangGraph Runtime            │  ← agent execution + memory
│        (ReAct + MemorySaver)        │
└───────────────────┬─────────────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
┌───────────────┐     ┌─────────────────┐
│  Tools        │     │  LangSmith      │
│  (web_search, │     │  (traces/evals) │
│   calculator, │     └─────────────────┘
│   your tools) │
└───────────────┘
```

---

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/your-org/controlpane
cd controlpane
cp .env.example .env
# Fill in OPENAI_API_KEY and optionally LANGCHAIN_API_KEY

# 2. Start everything
docker compose up

# 3. Open the chat UI
open http://localhost:3000

# 4. Or call the API directly
curl -X POST http://localhost:8000/agents/chat-agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "What is LangGraph?"}'
```

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Agent Manifest Format

Every agent is defined by a YAML file in `/manifests/`. ControlPane hot-reloads on change.

```yaml
name: research-agent
version: "1.0.0"
description: "A web research agent that searches and summarizes"

model:
  provider: openai        # openai | anthropic
  name: gpt-4o
  temperature: 0.0
  max_tokens: null        # optional

tools:
  - name: web_search      # must match a registered tool name
    description: "Search the web for information"
    input_schema:
      query: string
  - name: calculator
    description: "Perform math calculations"
    input_schema:
      expression: string

prompts:
  system: |
    You are a research assistant. Use tools to answer questions accurately.

state:
  schema:
    messages: list
    context: string

observability:
  trace: true
  eval_tags:
    - research
    - production
```

---

## How to Add a New Agent

1. Create `manifests/my-agent.yaml` using the format above
2. That's it — ControlPane picks it up automatically (no restart needed)

```bash
# Test your new agent
curl -X POST http://localhost:8000/agents/my-agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
```

---

## How to Add a New Tool

Create `tools/my_tool.py`:

```python
from langchain_core.tools import tool
from gateway.core.tool_registry import register

@register
@tool
def my_tool(input: str) -> str:
    """What this tool does. Input: description of the input."""
    # your implementation
    return result
```

Then reference it by name in any manifest:

```yaml
tools:
  - name: my_tool
    description: "Does the thing"
    input_schema:
      input: string
```

Tools are auto-discovered from the `/tools` directory on startup.

---

## Observability (LangSmith)

Set these in `.env`:

```env
LANGCHAIN_API_KEY=your_key_here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=controlpane
```

Every agent invocation is automatically traced. Traces appear at [smith.langchain.com](https://smith.langchain.com) under the `controlpane` project.

Check tracing status:
```bash
curl http://localhost:8000/health
# {"status": "ok", "tracing": true}
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Gateway info |
| GET | `/health` | Health + tracing status |
| GET | `/agents` | List all loaded agents |
| POST | `/agents/{name}/invoke` | Invoke agent (sync) |
| POST | `/agents/{name}/stream` | Invoke agent (SSE stream) |
| GET | `/manifests` | List all manifests |
| GET | `/manifests/{name}` | Get manifest detail |
| GET | `/openai/v1/models` | OpenAI-compat model list |
| POST | `/openai/v1/chat/completions` | OpenAI-compat chat endpoint |

### Invoke Request

```json
{
  "message": "What is the capital of France?",
  "thread_id": "optional-uuid-for-memory",
  "metadata": {}
}
```

### Invoke Response

```json
{
  "thread_id": "abc-123",
  "output": "The capital of France is Paris.",
  "tool_calls": [],
  "trace_url": "https://smith.langchain.com/...",
  "latency_ms": 842.5
}
```

---

## Phase Roadmap

### Phase 1 — Option B Done Right (current)
- YAML manifest → LangGraph agent compilation
- FastAPI gateway with clean REST + SSE API
- OpenAI-compatible endpoint for OpenWebUI
- LangSmith tracing from day one
- Tool registry with auto-discovery
- Thread-based memory (MemorySaver)
- Automated test suite (unit + API)

### Phase 2 — Pattern Extraction
- Prompt versioning and management
- Multi-model routing (route by cost, capability)
- Environment promotion (local → staging → prod)
- Eval harness integration
- Agent-to-agent tool calling

### Phase 3 — Full Control Plane
- Visual manifest editor (round-trip code ↔ visual)
- Deployment pipeline (one manifest → one deploy)
- Policy layer (rate limits, auth, cost caps)
- Registry for shared tools and prompts
- Team collaboration and versioning

---

## Comparison

| | ControlPane | Dify | Langflow | DIY Stack |
|---|---|---|---|---|
| YAML-first agent definition | ✅ | ❌ | ❌ | You build it |
| LangGraph runtime | ✅ | ❌ | Partial | You integrate |
| LangSmith tracing | ✅ built-in | ❌ | Optional | You wire it |
| OpenWebUI compatible | ✅ | ✅ | ✅ | You build it |
| Code + visual round-trip | Phase 3 | Partial | ✅ | No |
| Production-grade agents | ✅ | Limited | Limited | Yes, manually |
| No vendor lock-in | ✅ | Partial | Partial | ✅ |

---

## Testing

ControlPane ships with a full unit and API test suite covering all Phase 1 components.

### Install test dependencies

```bash
pip install -r requirements-dev.txt
```

### Run all tests

```bash
pytest tests/
```

### Test coverage

| Area | Tests | What's covered |
|------|-------|----------------|
| Models | 31 | Pydantic validation, defaults, required fields |
| ManifestLoader | 13 | YAML loading, hot-reload, caching, error handling |
| Tool registry | 13 | Registration, lookup, auto-discovery |
| Observability | 7 | LangSmith config, trace URL generation |
| Calculator tool | 15 | Arithmetic, operator safety, error paths |
| Web search tool | 15 | Tavily/DuckDuckGo, mocked HTTP, provider selection |
| RuntimeRegistry | 9 | Caching, invalidation on mtime/version change |
| API — health | 5 | Status, tracing flag |
| API — root | 6 | Gateway info shape |
| API — manifests | 12 | List, get, 404 |
| API — agents | 24 | List, invoke, stream, 404/500 |
| API — OpenAI compat | 24 | Models list, sync/stream completions |
| **Total** | **174** | |

Tests use FastAPI's `TestClient` with a mock runtime — no LLM API calls required.

---

## Project Structure

```
controlpane/
├── docker-compose.yml
├── .env.example
├── pytest.ini
├── requirements-dev.txt
├── manifests/                # Agent definitions (YAML)
│   ├── chat-agent.yaml
│   └── research-agent.yaml
├── tools/                    # Tool implementations
│   ├── base.py
│   ├── calculator.py
│   └── web_search.py
├── gateway/                  # FastAPI gateway
│   ├── main.py
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── core/
│   │   ├── manifest_loader.py
│   │   ├── runtime.py
│   │   ├── tool_registry.py
│   │   └── observability.py
│   ├── models/
│   │   ├── manifest.py
│   │   └── runtime.py
│   └── routers/
│       ├── agents.py
│       ├── manifests.py
│       ├── health.py
│       └── openai_compat.py
└── tests/                    # Automated test suite
    ├── conftest.py
    ├── unit/
    │   ├── test_models.py
    │   ├── test_manifest_loader.py
    │   ├── test_tool_registry.py
    │   ├── test_observability.py
    │   ├── test_calculator.py
    │   ├── test_web_search.py
    │   └── test_runtime.py
    └── api/
        ├── test_health.py
        ├── test_root.py
        ├── test_manifests.py
        ├── test_agents.py
        └── test_openai_compat.py
```

---

## Contributing

ControlPane is intentionally thin in Phase 1. Before adding abstractions, validate them with real usage.

The rule: **if removing LangGraph tomorrow would break your agent's business logic, you've built glue, not architecture.** ControlPane's job is to prevent that.
