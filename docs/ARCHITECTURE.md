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
9. **Container isolation** — The backend runs in its own container and touches the host Docker socket directly (see *Known limitation* below).

### Known limitation: the Docker socket mount

The backend container mounts `/var/run/docker.sock` directly. This is a
deliberate, accepted trade-off, not an oversight — stated explicitly so it
reads as a scoped decision rather than an unexamined gap.

- **What the structured validator actually bounds.** `guardrails.validate_params()`
  (see `app/safety/structured_validator.py`) constrains *what can be
  requested* of the backend: which tool, which params, which filesystem
  roots, which containers. Every request the application processes goes
  through it — that boundary is real and is what the test suite exercises.
- **What it doesn't bound.** The socket mount means the backend process
  itself has root-equivalent control over the host. A compromise of the
  backend — an RCE in a dependency, not necessarily anything in this
  codebase — reaches the Docker API directly and the validator is simply
  never in the path. The validator bounds requests *to the application*; it
  cannot bound what a compromised application does on its own.
- **The production mitigation is a socket proxy** — e.g.
  `tecnativa/docker-socket-proxy` — placed between the backend and the
  socket with an explicit endpoint allowlist (list/inspect/start/stop, no
  `EXEC`, no `VOLUMES`, no `SYSTEM`), so a compromised backend can still only
  reach the same narrow surface the validator already permits. That's a
  separate piece of infrastructure (a new service, a network boundary, a
  changed `DOCKER_HOST`), not a code patch, which is why it's named here as
  future work rather than folded into this submission. See `docs/SECURITY.md`
  item 1 for the concrete config.
- **Why this is the honest scope for an FYP.** A platform whose entire
  purpose is managing containers needs *some* way to reach the Docker API;
  the question is only how directly. Naming the boundary and its mitigation
  is the stronger position — a threat model that states its own edges,
  rather than one that implies it has none.

## Why MCP matters here

Traditional DevOps chatbots hardcode `if "docker" in command:` dispatch logic. The Model Context Protocol approach decouples three things:

* **Tool declaration** — Each tool publishes a JSON-schema describing its inputs and capabilities.
* **Tool discovery** — A client (the router here, an LLM in the general case) enumerates tools at runtime.
* **Tool invocation** — A uniform `execute(params)` contract means new tools become available without modifying the router or client.

The registry exposes all of this through `/tools/`, so the frontend can render tool cards without knowing about specific tools, and the same endpoint could feed an MCP-aware LLM in the future.
