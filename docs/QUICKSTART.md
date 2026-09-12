# Quick-Start Guide (macOS + Docker Desktop)

## 1. Prerequisites

* macOS 12+
* Docker Desktop 4.20+ running
* `make`, `git`, `curl`, `jq`

```bash
brew install make git curl jq
```

## 2. Clone + configure

```bash
git clone <your-repo> devops-mcp-platform
cd devops-mcp-platform
cp .env.example .env
```

## 3. Launch

```bash
make up
```

You should see three containers come up: `mcp-postgres`, `mcp-backend`, `mcp-frontend`.

## 4. Open the UI

<http://localhost:3000>

API docs: <http://localhost:8000/docs>

## 5. Run the demo

```bash
bash scripts/seed_sample_data.sh   # seeds sample_data/sample.log
make demo                           # fires 10 representative commands
```

## 6. Try these commands in the web UI

* `system health`
* `disk usage`
* `memory usage`
* `list all containers`
* `deploy nginx on port 8080`  _(tick "Dry-run" first to practice)_
* `analyze logs at /data/sample.log`  _(when running inside compose; the sample_data folder is mounted at /data)_
* `count lines in /data/sample.log`
* `stop mcp-managed-nginx`  _(destructive — submit once to see the confirmation prompt, then confirm to run it)_

## 7. Tear down

```bash
make down              # stop services, keep the database
make clean             # stop + delete the volume
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `docker: Cannot connect to the Docker daemon` | Start Docker Desktop, wait for whale icon |
| `address already in use :3000` | Another Next.js is running; `lsof -i :3000` |
| Postgres exits immediately | Try `make clean` to reset the volume |
| Frontend shows "offline" | Backend not up yet — `make logs-backend` |
| Commands 500, `make logs-backend` shows `UndefinedColumn` on `audit_logs` | Your `mcp_postgres_data` volume predates a schema change — `create_all()` creates new tables but never alters existing ones. Run `make migrate` (now also run automatically by `make up`). |
