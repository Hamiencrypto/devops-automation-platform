# AI-Powered DevOps Automation Platform with MCP Routing

A web-based platform that accepts **natural-language DevOps commands** and routes them through an **MCP (Model Context Protocol)** tool registry for execution — no CLI expertise required.

> **Final Year Project — University of Sindh, Jamshoro**
> Department of Information Technology, Faculty of Engineering and Technology

---

## What this does

Type an English sentence, get DevOps work done:

| You type | System does |
|---|---|
| `deploy nginx on port 8080` | Pulls image, runs container, exposes port |
| `list all containers` | Enumerates every Docker container |
| `analyze logs at /var/log/app.log` | Counts errors/warnings, samples top messages |
| `count lines in package.json` | Returns line count |
| `system health` | Reports CPU, load, disk, memory |
| `stop mcp-managed-nginx` | Stops container (requires confirmation — destructive) |
| `scale web to 5` | Scales Kubernetes deployment (if kubectl available) |

---

## What makes it better than the original spec

The baseline FYP called for three tools and regex intent detection. This implementation extends that substantially:

1. **Five MCP tools instead of three** — Docker, Logs, File, **Kubernetes**, and **System** inspection, all registered through a single MCP-compliant registry.
2. **Safety layer** — Destructive actions (`stop`, `remove`, `scale`) require explicit `confirm_destructive=true`. A banned-pattern filter blocks things like `rm -rf /` and fork bombs. A rolling per-user rate limiter caps 30 commands/minute by default.
3. **Dry-run mode** — Every tool accepts `dry_run=true` to describe what it *would* do without touching anything. Perfect for demos and for validating CI pipelines.
4. **Audit trail** — Every command, block, and crash writes a structured row to `audit_logs` with severity, user, IP, and full details. Satisfies enterprise-grade compliance expectations.
5. **JWT auth + RBAC** — Optional bearer-token auth with three roles (`admin`, `developer`, `viewer`). Off by default for the demo, flip `ENABLE_AUTH=true` to turn on.
6. **Real-time log streaming over WebSockets** — Connect to `ws://.../ws/logs/<container>` and receive live log lines as JSON frames.
7. **Confidence scoring on intents** — The regex engine returns a 0–1 confidence score computed from pattern weight × match coverage. The UI surfaces this. Low-confidence matches generate a warning.
8. **Tool catalog API** — `/tools/` returns MCP-compliant JSON schemas for every registered tool, so the UI and any MCP client can discover capabilities dynamically.
9. **Graceful degradation** — Each tool handles absent dependencies (no Docker daemon, no kubectl, no `/proc/meminfo`) without crashing the API.
10. **Full Docker Compose orchestration** — `make up` launches Postgres + backend + frontend in one command on macOS, Linux, or WSL2.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14, React 18, TypeScript 5, Tailwind CSS 3, lucide-react icons |
| Backend | FastAPI 0.109, Python 3.11, SQLAlchemy 2, Pydantic v2 |
| Intent engine | Pure Python regex with weighted confidence scoring |
| MCP | Custom, spec-compliant tool registry + dynamic router |
| Database | PostgreSQL 15 |
| Container runtime | Docker + Docker Compose v2 |
| Auth | JWT via `python-jose`, password hashing via `bcrypt` |
| Testing | pytest + pytest-asyncio |

---

## Quick start (macOS + Docker Desktop)

```bash
# 1. Clone
git clone <your-repo>.git
cd devops-mcp-platform

# 2. Copy environment template
cp .env.example .env

# 3. Seed a sample log file for the demo
bash scripts/seed_sample_data.sh

# 4. Launch the stack
make up

# 5. Open the UI
open http://localhost:3000
```

The API docs are auto-generated at <http://localhost:8000/docs>.

To run the scripted demo against the live API:

```bash
make demo
```

---

## Project layout

```
devops-mcp-platform/
├── backend/                     FastAPI service
│   ├── app/
│   │   ├── main.py              App entry point
│   │   ├── config.py            Pydantic settings
│   │   ├── database.py          SQLAlchemy engine + sessions
│   │   ├── models.py            User, Task, Result, AuditLog
│   │   ├── schemas.py           Pydantic DTOs
│   │   ├── auth.py              JWT + RBAC helpers
│   │   ├── intent/              Regex intent engine
│   │   │   ├── engine.py        IntentEngine.detect()
│   │   │   └── patterns.py      Weighted pattern list
│   │   ├── mcp/                 MCP Router + Registry
│   │   │   ├── registry.py      ToolRegistry
│   │   │   └── router.py        MCPRouter
│   │   ├── tools/               Five MCP tools
│   │   │   ├── base.py          MCPTool + ToolResult
│   │   │   ├── docker_tool.py
│   │   │   ├── logs_tool.py
│   │   │   ├── file_tool.py
│   │   │   ├── kubernetes_tool.py
│   │   │   └── system_tool.py
│   │   ├── api/                 FastAPI routers
│   │   │   ├── execute.py       POST /execute
│   │   │   ├── tasks.py         GET /tasks
│   │   │   ├── tools.py         GET /tools
│   │   │   ├── auth.py          POST /auth/login
│   │   │   └── websocket.py     WS /ws/logs/{name}
│   │   ├── safety/              Guardrails + audit
│   │   └── services/            Executor pipeline
│   ├── tests/                   Pytest suite
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                    Next.js UI
│   ├── src/
│   │   ├── app/                 page.tsx, layout.tsx
│   │   ├── components/          CommandInput, Results, History, ToolsList
│   │   └── lib/api.ts           API client
│   ├── Dockerfile
│   ├── package.json
│   └── tailwind.config.ts
├── scripts/
│   ├── demo.sh                  Scripted end-to-end demo
│   └── seed_sample_data.sh
├── sample_data/                 Demo logs
├── docs/                        Architecture + API docs
├── docker-compose.yml
├── .env.example
├── Makefile
└── README.md
```

---

## How a command flows through the system

1. User types a sentence in the web UI.
2. UI posts `{"command": "...", "dry_run": false, "confirm_destructive": false}` to `POST /execute`.
3. `executor.execute_command()` creates a `Task` row in Postgres.
4. **Rate limiter** checks against the per-user/IP sliding window.
5. **Intent engine** (`IntentEngine.detect`) runs every pattern and returns `(intent, confidence, entities)`.
6. **Guardrails** check for banned tokens, low confidence, and destructive-without-confirmation.
7. **MCP Router** (`MCPRouter.route`) looks up the tool registered for this intent and validates required params.
8. The tool's `execute(params, dry_run)` runs and returns a `ToolResult`.
9. Result is persisted to `results` table; `audit_logs` entry is written.
10. API returns the full `ExecuteResponse` — task id, intent, tool call, result, warnings, duration.

---

## Running the tests

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

Tests cover the intent engine, MCP router/registry, and safety layer.

---

## Adding a new MCP tool

Because every tool is a self-contained subclass that registers itself with the global registry, extending the platform is a one-file change.

1. Create `backend/app/tools/my_tool.py`:

```python
from app.mcp.registry import tool_registry
from app.tools.base import MCPTool, ToolResult

class MyTool(MCPTool):
    name = "my_tool"
    description = "Does something useful"
    category = "custom"
    intents = ("my.action",)
    input_schema = {
        "type": "object",
        "properties": {"action": {"type": "string"}},
        "required": ["action"],
    }

    def execute(self, params, dry_run=False):
        return self.ok("Did the thing", **params)

tool_registry.register(MyTool())
```

2. Import it in `backend/app/tools/__init__.py` so it loads on startup.
3. Add a regex pattern for the new intent in `backend/app/intent/patterns.py`.
4. Done — no router changes, no frontend changes, no redeploy of unrelated services.

---

## References

* Anthropic — *Model Context Protocol specification* (2024)
* FastAPI — <https://fastapi.tiangolo.com/>
* Docker SDK for Python — <https://docker-py.readthedocs.io/>
* PostgreSQL 15 docs — <https://www.postgresql.org/docs/15/>
* Next.js 14 App Router — <https://nextjs.org/docs/app>

---

## License & credits

Built as a Final Year Project for the Department of Information Technology, University of Sindh, Jamshoro.
