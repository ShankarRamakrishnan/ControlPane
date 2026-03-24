# ControlPane

Run and manage AI agents without chaos.

ControlPane is a control plane for AI systems:
- define agents once (YAML)
- run them consistently (LangGraph)
- observe everything (LangSmith)
- use from UI or API (OpenWebUI compatible)

Stop writing glue code. Start running experiments.

---

## The problem

If you've built anything with LangChain / LangGraph:

- every agent has a different structure
- tools are wired differently every time
- prompts live in random files
- debugging is painful
- nothing is reusable

So every project starts from scratch.

You don't have a system. You have glue code.

---

## What you can do in 2 minutes

1. Define an agent in YAML
2. Start ControlPane
3. Use it from UI or API

That's it. No wiring. No custom runtime. No repeated setup.

```bash
git clone https://github.com/your-org/controlpane
cd controlpane
cp .env.example .env   # add OPENAI_API_KEY
docker compose up

# call your agent
curl -X POST http://localhost:8000/agents/research-agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "Summarize the latest news on LLMs"}'
```

Open the chat UI: [http://localhost:3000](http://localhost:3000) — powered by OpenWebUI, no extra config needed.

---

## Think of it like this

```
LangGraph   = runtime
LangSmith   = observability
ControlPane = control plane
```

You already use the first two. ControlPane is the missing layer that connects them.

---

## Example: run 50 research agents in parallel

- same task
- different prompts / models
- compare outputs side by side
- pick the best

ControlPane lets you do this without writing custom orchestration code. Define each variant as a YAML manifest, hit the API, collect results.

---

## Agent manifests (your wedge)

Every agent is a YAML file. ControlPane hot-reloads on change — no restart needed.

```yaml
name: research-agent
version: "1.0.0"
description: "A web research agent that searches and summarizes"

model:
  provider: openai
  name: gpt-4o
  temperature: 0.0

tools:
  - name: web_search
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

observability:
  trace: true
  eval_tags:
    - research
    - production
```

Add a new agent: create a file. That's it.

```bash
# your new agent is live immediately
curl -X POST http://localhost:8000/agents/my-agent/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
```

---

## Add a tool in one file

```python
# tools/my_tool.py
from langchain_core.tools import tool
from gateway.core.tool_registry import register

@register
@tool
def my_tool(input: str) -> str:
    """What this tool does. Input: description of the input."""
    return result
```

Reference it by name in any manifest. Tools are auto-discovered on startup.

---

## Observability (automatic)

Set three env vars:

```env
LANGCHAIN_API_KEY=your_key_here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=controlpane
```

Every invocation is traced automatically. No instrumentation code. Traces appear at [smith.langchain.com](https://smith.langchain.com) under your project.

```bash
curl http://localhost:8000/health
# {"status": "ok", "tracing": true}
```

---

## Architecture

```
┌─────────────────────────────────────┐
│           OpenWebUI  (port 3000)    │  ← chat UI
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
| POST | `/openai/v1/chat/completions` | OpenAI-compat chat |

**Request:**
```json
{
  "message": "What is the capital of France?",
  "thread_id": "optional-uuid-for-memory"
}
```

**Response:**
```json
{
  "thread_id": "abc-123",
  "output": "The capital of France is Paris.",
  "tool_calls": [],
  "trace_url": "https://smith.langchain.com/...",
  "latency_ms": 842.5
}
```

Full docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Comparison

| | ControlPane | Dify | Langflow | DIY Stack |
|---|---|---|---|---|
| YAML-first agent definition | ✅ | ❌ | ❌ | You build it |
| LangGraph runtime | ✅ | ❌ | Partial | You integrate |
| LangSmith tracing | ✅ built-in | ❌ | Optional | You wire it |
| OpenWebUI compatible | ✅ | ✅ | ✅ | You build it |
| No vendor lock-in | ✅ | Partial | Partial | ✅ |
| Production-grade agents | ✅ | Limited | Limited | Yes, manually |

---

## Testing

174 tests. No LLM API calls required — the suite uses a mock runtime.

```bash
pip install -r requirements-dev.txt
pytest tests/
```

| Area | Tests |
|------|-------|
| Models | 31 |
| ManifestLoader | 13 |
| Tool registry | 13 |
| Observability | 7 |
| Calculator tool | 15 |
| Web search tool | 15 |
| RuntimeRegistry | 9 |
| API (health, root, manifests, agents, OpenAI compat) | 71 |
| **Total** | **174** |

---

## Roadmap

**Now**
- YAML manifest → LangGraph agent compilation
- FastAPI gateway with REST + SSE
- OpenAI-compatible endpoint for OpenWebUI
- LangSmith auto-tracing
- Tool registry with auto-discovery
- Thread-based memory

**Next**
- Prompt versioning and management
- Multi-model routing (by cost, capability)
- Environment promotion (local → staging → prod)
- Eval harness integration
- Agent-to-agent tool calling

**Later**
- Visual manifest editor
- Deployment pipeline
- Policy layer (rate limits, auth, cost caps)
- Shared tool and prompt registry
- Team collaboration and versioning

---

## Project structure

```
controlpane/
├── docker-compose.yml
├── .env.example
├── manifests/                # Agent definitions (YAML)
│   ├── chat-agent.yaml
│   └── research-agent.yaml
├── tools/                    # Tool implementations
│   ├── calculator.py
│   └── web_search.py
├── gateway/                  # FastAPI gateway
│   ├── main.py
│   ├── core/
│   │   ├── manifest_loader.py
│   │   ├── runtime.py
│   │   ├── tool_registry.py
│   │   └── observability.py
│   └── routers/
│       ├── agents.py
│       ├── manifests.py
│       ├── health.py
│       └── openai_compat.py
└── tests/
    ├── unit/
    └── api/
```

---

## Contributing

ControlPane is intentionally thin. Before adding abstractions, validate them with real usage.

The rule: **if removing LangGraph tomorrow would break your agent's business logic, you've built glue, not architecture.** ControlPane's job is to prevent that.
