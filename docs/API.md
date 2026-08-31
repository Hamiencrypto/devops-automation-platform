# API Reference

Base URL: `http://localhost:8000`
Interactive docs: `http://localhost:8000/docs`

---

## Health

### `GET /health`

Returns liveness + dependency checks.

```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "development",
  "checks": {
    "api": "ok",
    "tools_loaded": "5",
    "database": "ok",
    "docker": "ok"
  }
}
```

---

## Execute

### `POST /execute`

Run a natural-language DevOps command.

**Request body**

```json
{
  "command": "deploy nginx on port 8080",
  "dry_run": false,
  "confirm_destructive": false
}
```

**Response**

```json
{
  "task_id": 12,
  "status": "success",
  "intent": {
    "intent": "docker.deploy",
    "confidence": 0.85,
    "entities": { "image": "nginx", "port": 8080 }
  },
  "tool_call": {
    "tool_name": "docker_manager",
    "params": { "action": "deploy", "image": "nginx", "port": 8080 }
  },
  "result": {
    "success": true,
    "summary": "Deployed nginx as 'mcp-managed-nginx' on port 8080",
    "data": { "container_id": "abc123", "host_port": 8080 },
    "stdout": "",
    "stderr": "",
    "warnings": []
  },
  "summary": "Deployed nginx as 'mcp-managed-nginx' on port 8080",
  "duration_ms": 843,
  "warnings": []
}
```

**Status values**

* `success` — tool ran and reported success
* `failed` — tool ran and reported failure
* `blocked` — safety layer refused to execute
* `dry_run` — plan returned, no side effects
* `running`, `pending` — transient

---

## Tasks

### `GET /tasks/?page=1&page_size=20&status=success&intent=docker.list`

Returns paginated task history.

### `GET /tasks/{task_id}`

Returns a single task record.

### `GET /tasks/{task_id}/result`

Returns the raw tool output for a task.

---

## Tools

### `GET /tools/`

Returns the MCP tool catalog.

```json
{
  "total": 5,
  "tools": [
    {
      "name": "docker_manager",
      "description": "Manage Docker containers: ...",
      "input_schema": { "type": "object", "properties": { ... } },
      "intents": ["docker.deploy", "docker.list", ...],
      "destructive": false,
      "category": "docker"
    }
  ]
}
```

### `GET /tools/intents`

Returns every registered intent name.

### `GET /tools/{tool_name}`

Returns the JSON schema for a single tool.

---

## Auth (optional, off by default)

Enable by setting `ENABLE_AUTH=true` in `.env`.

### `POST /auth/register`

```json
{ "username": "alice", "email": "alice@uni.edu", "password": "s3cret12", "role": "developer" }
```

### `POST /auth/login`

Form-encoded (OAuth2 password flow):

```
username=alice&password=s3cret12
```

Returns:

```json
{ "access_token": "eyJ...", "token_type": "bearer", "expires_in": 86400 }
```

Use in subsequent requests:

```
Authorization: Bearer eyJ...
```

---

## WebSockets

### `WS /ws/logs/{container_name}`

Streams live Docker container logs. Server sends JSON frames:

```json
{"event": "connected", "container": "mcp-managed-nginx"}
{"line": "2026-04-19 10:00:01 GET /", "timestamp": "2026-04-19T10:00:01.123"}
```

### `WS /ws/events`

Echo endpoint reserved for future task status broadcasts.

---

## Error shapes

Every error returns the standard FastAPI shape:

```json
{ "detail": "Human-readable message" }
```

Common status codes: `400` (validation), `401` (auth), `403` (role), `404` (not found), `429` (rate limit), `500` (unexpected).
