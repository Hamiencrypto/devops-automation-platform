# Security fixes — apply these before enabling the LLM

The validator closes the parameter surface. These three close the holes
underneath it. Order matters: a perfect validator in front of a container that
already has host root is theatre.

> **Status (2026-09-11):** Item 4's exact code below is stale — the live
> wiring in `guardrails.py`/`executor.py` took a simpler shape than what's
> sketched here, already tested and working. In the course of applying that,
> a live instance of exactly the gap item 4 warns about was found and fixed:
> `backend/app/api/containers.py`'s stop/remove-by-ID endpoints built tool
> params from the URL and called `tool.execute()` directly, never through
> `guardrails.validate_params()` — so the protected-container policy in
> item 1 could be bypassed entirely through that route regardless of whether
> the socket is proxied. Fixed; see `tests/test_containers_api.py`.
> Items **1** (docker-socket proxy) and **3** (production-auth guard) are
> still open — the socket is still mounted directly
> (`docker-compose.yml`, `/var/run/docker.sock`) and `config.py` has no
> production validator. Item **2** (tools re-validating their own path
> instead of trusting the caller) is also still open, and is a reasonable
> defense-in-depth follow-up now that containers.py shows a second caller can
> exist.

---

## 1. Docker socket → proxy

Right now the backend mounts `/var/run/docker.sock`. The Docker API has no
internal authorisation, so a process that can reach that socket can start a
container with the host filesystem bind-mounted and write to it as root. Any
RCE in the backend — including one you have not found yet — is a host
compromise, not an application compromise.

The proxy puts an allowlist in front of the API. The backend never sees the
socket.

`docker-compose.yml`:

```yaml
services:
  docker-proxy:
    image: tecnativa/docker-socket-proxy:0.2.0
    container_name: docker-proxy
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      # Default in this image is deny; only these are opened.
      - CONTAINERS=1      # list, inspect, start, stop
      - IMAGES=1          # pull, list
      - POST=1            # required for start/stop; without it everything is read-only
      - INFO=1
      - VERSION=1
      # Everything below stays off. EXEC=1 in particular would hand back
      # arbitrary code execution inside any container and undo the whole point.
      - EXEC=0
      - NETWORKS=0
      - VOLUMES=0
      - SECRETS=0
      - CONFIGS=0
      - SWARM=0
      - NODES=0
      - PLUGINS=0
      - SYSTEM=0
      - AUTH=0
      - BUILD=0
      - COMMIT=0
      - DISTRIBUTION=0
      - SERVICES=0
      - SESSION=0
      - TASKS=0
    networks: [internal]
    restart: unless-stopped

  backend:
    # REMOVE the socket mount entirely:
    #   volumes:
    #     - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - DOCKER_HOST=tcp://docker-proxy:2375
    depends_on: [docker-proxy]
    networks: [internal, public]

networks:
  internal:
    internal: true   # no route off the host; the proxy is unreachable from outside
  public:
```

`backend/app/tools/docker_tool.py` — pick up the host from the environment:

```python
import os
import docker

def _client():
    # docker.from_env() already reads DOCKER_HOST, but being explicit here
    # means a misconfiguration fails loudly instead of silently falling back
    # to a local socket that may or may not be mounted.
    host = os.getenv("DOCKER_HOST")
    if not host:
        raise RuntimeError("DOCKER_HOST is not set; refusing to guess a Docker endpoint")
    return docker.DockerClient(base_url=host, timeout=15)
```

Honest limitation to state in the viva rather than let an examiner find it:
`CONTAINERS=1` plus `POST=1` still allows creating containers, and container
creation with a bind mount is itself privilege escalation. The proxy narrows
the API surface; it does not make it safe on its own. The `policy_docker`
checks (no privileged, no host network, no socket mount, no arbitrary bind
mounts) are what close that, which is exactly why the policy layer exists and
why `EXEC=0` matters. Defence in depth, and you can say precisely which layer
stops which attack.

---

## 2. `backend/app/tools/file_tool.py`

The tool should not re-implement containment. It should refuse to run on a
path the validator has not already blessed, so there is one implementation of
the rule and no chance of the two drifting apart.

```python
from app.safety.structured_validator import SafetyPolicy, check_path

class FileTool(MCPTool):
    name = "file_tool"
    # ... schema unchanged

    def __init__(self, policy: SafetyPolicy | None = None):
        self.policy = policy or SafetyPolicy()

    def execute(self, params, dry_run=False):
        # Belt and braces. The validator already ran in guardrails, but a tool
        # that is safe only because of its caller is a tool waiting to be
        # called from somewhere else.
        checked = check_path(params.get("path", ""), self.policy)
        if not checked:
            return self.error(checked.reason)

        path = Path(checked.params["path"])
        if dry_run:
            return self.ok(f"Would read {path.name}", path=str(path))

        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                lines = sum(1 for _ in fh)
        except FileNotFoundError:
            return self.error("File not found.")
        except PermissionError:
            return self.error("File is not readable.")
        except OSError as exc:
            return self.error(f"File could not be read: {exc}")

        return self.ok(f"{lines} lines", path=str(path), lines=lines)
```

Apply the same to `logs_tool.py`. It reads arbitrary paths too, and it is the
one people forget.

Create the sandbox in the backend `Dockerfile`:

```dockerfile
RUN mkdir -p /app/safe_data /app/sample_data \
    && chown -R appuser:appuser /app/safe_data /app/sample_data
```

---

## 3. Auth default

Leaving `ENABLE_AUTH=false` is defensible for a demo, but it must be loud and
it must be impossible to ship by accident.

`backend/app/config.py`:

```python
    ENABLE_AUTH: bool = False
    ENVIRONMENT: str = "development"   # development | staging | production
    JWT_SECRET: str = ""

    # --- structured validator ---
    ALLOWED_FILE_ROOTS: str = "/app/safe_data,/app/sample_data"
    MAX_FILE_BYTES: int = 10_485_760
    MIN_BINDABLE_PORT: int = 1024
    MAX_REPLICAS: int = 10

    @model_validator(mode="after")
    def _production_requires_auth(self):
        if self.ENVIRONMENT == "production":
            if not self.ENABLE_AUTH:
                raise ValueError("ENABLE_AUTH must be true when ENVIRONMENT=production")
            if len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
            if self.LLM_API_KEY and self.LLM_API_KEY.startswith("your_"):
                raise ValueError("LLM_API_KEY is still the placeholder value")
        return self
```

A failed startup is a good outcome here. The alternative is a production
deployment that comes up cheerfully with no authentication.

Add to `main.py` startup:

```python
@app.on_event("startup")
async def warn_if_open():
    if not settings.ENABLE_AUTH:
        log.warning(
            "AUTHENTICATION IS DISABLED. Every endpoint is public. "
            "Set ENABLE_AUTH=true before exposing this service."
        )
```

And surface it in the UI — a persistent banner when `/health` reports
`auth_enabled: false`. An examiner who sees the platform telling on itself
reads that as maturity, not as a defect.

---

## 4. Wiring the validator in

`backend/app/services/executor.py`:

```python
from functools import lru_cache

from app.config import settings
from app.mcp.registry import tool_registry
from app.safety.guardrails import Guardrails
from app.safety.structured_validator import SafetyPolicy, StructuredOutputValidator


@lru_cache(maxsize=1)
def get_guardrails() -> Guardrails:
    validator = StructuredOutputValidator(
        tool_registry, SafetyPolicy.from_settings(settings)
    )
    return Guardrails(validator)
```

In `execute_command()`, before intent detection:

```python
    guards = get_guardrails()

    raw = guards.check_raw(command)
    if not raw:
        audit.write(action="command.blocked", severity="warning",
                    details={"reason": raw.reason})
        return ExecuteResponse(task_id=task.id, success=False, message=raw.reason)
```

After intent detection and tool resolution:

```python
    decision = guards.check(
        intent,
        tool.name,
        confirm_destructive=confirm_destructive,
        user_role=user.role if user else "developer",
    )

    if decision.requires_approval:
        task.approval_status = "pending"
        session.commit()
        return ExecuteResponse(task_id=task.id, success=False,
                               message=decision.reason, warnings=decision.warnings)

    if not decision:
        audit.write(action="command.blocked", severity="warning",
                    details={"intent": intent.name, "reason": decision.reason,
                             "source": intent.source})
        return ExecuteResponse(task_id=task.id, success=False,
                               message=decision.reason, warnings=decision.warnings)

    # Execute with decision.params, NOT intent.entities — the validator
    # normalised the paths, and the checked value must be the used value.
    result = tool.execute(decision.params, dry_run=dry_run)
```

That last line is the one to get right. Validating one value and executing a
different one is a real bug class (time-of-check to time-of-use), and passing
`intent.entities` through after normalising into `decision.params` would
reintroduce exactly the symlink escape the tests cover.

---

## Verifying

```bash
cd backend
pip install jsonschema anthropic
PYTHONPATH=. pytest tests/test_structured_validator.py tests/test_llm_engine.py -v
```

Both suites run offline with no API key. Confirmed passing: 42 validator
tests, 30 engine tests.
