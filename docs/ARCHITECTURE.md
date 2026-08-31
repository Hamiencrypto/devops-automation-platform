# Architecture Reference

## High-level component diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        USER BROWSER                          │
│                    http://localhost:3000                     │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│            NEXT.JS FRONTEND (Port 3000)                      │
│  CommandInput · ResultsDisplay · TaskHistory · ToolsList     │
│                         api.ts                               │
└───────────────────────────────┬─────────────────────────────┘
                                │ HTTP / WebSocket
                                ▼
┌─────────────────────────────────────────────────────────────┐
│            FASTAPI BACKEND (Port 8000)                       │
│  POST /execute · GET /tasks · GET /tools · POST /auth/login  │
│  WS   /ws/logs/{container} · WS /ws/events                   │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│            EXECUTOR PIPELINE (app/services/executor.py)      │
│   1) RateLimiter  →  2) IntentEngine  →  3) Guardrails       │
│                →  4) MCPRouter  →  5) Tool.execute()         │
│                →  6) Persist + Audit                         │
└───────────────────────────────┬─────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌────────────────┐   ┌────────────────┐   ┌────────────────┐
│ IntentEngine   │   │  MCPRegistry   │   │  SafetyLayer   │
│ weighted regex │   │ by-intent map  │   │ banned tokens  │
│ conf scoring   │   │ schema export  │   │ destructive    │
│ entity extract │   │                │   │ rate limit     │
└────────────────┘   └────────┬───────┘   └────────────────┘
                              │
     ┌─────────┬─────────┬────┴────┬─────────┬─────────┐
     ▼         ▼         ▼         ▼         ▼         ▼
┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
│Docker  ││ Logs   ││  File  ││  K8s   ││ System │
│Tool    ││ Tool   ││ Tool   ││ Tool   ││  Tool  │
└───┬────┘└────────┘└────────┘└────────┘└────────┘
    │
    ▼
┌─────────────────────┐
│ Docker Engine       │
│ /var/run/docker.sock│
└─────────────────────┘

                                ▼
┌─────────────────────────────────────────────────────────────┐
│                POSTGRESQL (Port 5432)                        │
│   users · tasks · results · audit_logs                       │
└─────────────────────────────────────────────────────────────┘
```

## Separation of concerns

| Layer | Responsibility | Key files |
|---|---|---|
| **Presentation** | React components, API client, styling | `frontend/src/*` |
| **Transport** | HTTP request/response, CORS, WebSocket | `backend/app/api/*` |
| **Orchestration** | Pipeline sequencing, error handling | `backend/app/services/executor.py` |
| **Intent** | Natural language → structured intent | `backend/app/intent/*` |
| **Routing** | Intent → MCP tool dispatch | `backend/app/mcp/*` |
| **Execution** | Actual DevOps work via system APIs | `backend/app/tools/*` |
| **Safety** | Guardrails, rate limiting, audit | `backend/app/safety/*` |
| **Persistence** | ORM models, database schema | `backend/app/models.py`, `database.py` |

## Extensibility points

* **Add a new intent** — Drop a regex entry into `app/intent/patterns.py`. No other code changes.
* **Add a new MCP tool** — Subclass `MCPTool`, define `execute()`, call `tool_registry.register()`.
* **Swap the intent engine** — Replace `IntentEngine.detect()` with an LLM-backed implementation conforming to the same signature.
* **Add a new frontend panel** — Components are independent; the `fetchHealth`/`fetchTools`/`fetchTasks` hooks are reusable.

## Data model

```
┌────────────┐        ┌────────────┐        ┌────────────┐
│   User     │─1────∞─│    Task    │─1────1─│  Result    │
│            │        │            │        │            │
│ username   │        │ command    │        │ success    │
│ email      │        │ intent     │        │ summary    │
│ role       │        │ tool       │        │ data       │
│ password   │        │ status     │        │ stdout     │
└────────────┘        │ duration   │        │ stderr     │
                      │ dry_run    │        └────────────┘
                      └──────┬─────┘
                             │
                             ∞
                      ┌──────┴─────┐
                      │ AuditLog   │
                      │ event      │
                      │ severity   │
                      │ details    │
                      │ ip_address │
                      └────────────┘
```

## Security model

1. **Transport** — All traffic on the local Docker network. For production, front with a reverse proxy and TLS.
2. **Authentication** — JWT bearer tokens via `python-jose`. Toggle with `ENABLE_AUTH`.
3. **Authorization** — Three roles (`admin`, `developer`, `viewer`). Enforced via `require_role()` dependency.
4. **Input validation** — Pydantic v2 schemas on every endpoint.
5. **Banned patterns** — Regex blocklist of catastrophic commands (fork bombs, root deletion, disk writes).
6. **Destructive confirmations** — `docker.stop`, `docker.remove`, `k8s.scale` require explicit opt-in.
7. **Rate limiting** — Sliding window per user or IP; default 30 req/min.
8. **Audit logging** — Every privileged action persists a row with full context.
9. **Container isolation** — The backend runs in its own container and only touches the host Docker socket (read-write by design — this is a DevOps tool).

## Why MCP matters here

Traditional DevOps chatbots hardcode `if "docker" in command:` dispatch logic. The Model Context Protocol approach decouples three things:

* **Tool declaration** — Each tool publishes a JSON-schema describing its inputs and capabilities.
* **Tool discovery** — A client (the router here, an LLM in the general case) enumerates tools at runtime.
* **Tool invocation** — A uniform `execute(params)` contract means new tools become available without modifying the router or client.

The registry exposes all of this through `/tools/`, so the frontend can render tool cards without knowing about specific tools, and the same endpoint could feed an MCP-aware LLM in the future.
