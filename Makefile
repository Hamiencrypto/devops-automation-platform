# ====================================================================
# DevOps MCP Platform — developer convenience Makefile
# ====================================================================

.PHONY: help up down logs build rebuild restart test lint backend-shell \
        db-shell clean demo seed

help:  ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up:  ## Start the full stack (backend + frontend + db)
	docker compose up -d --build
	@echo ""
	@echo "  Backend:  http://localhost:8000"
	@echo "  Docs:     http://localhost:8000/docs"
	@echo "  Frontend: http://localhost:3000"

down:  ## Stop and remove all containers (keeps volumes)
	docker compose down

logs:  ## Tail logs for all services
	docker compose logs -f --tail=100

logs-backend:  ## Tail backend logs only
	docker compose logs -f --tail=100 backend

build:  ## Build images without starting
	docker compose build

rebuild:  ## Force rebuild with no cache
	docker compose build --no-cache

restart:  ## Restart all services
	docker compose restart

test:  ## Run backend tests
	docker compose exec backend pytest -v

lint:  ## Quick Python syntax check
	docker compose exec backend python -m py_compile app/main.py

backend-shell:  ## Open a bash shell in the backend container
	docker compose exec backend bash

db-shell:  ## Open a psql shell
	docker compose exec db psql -U devops -d devops_mcp

clean:  ## Stop everything and wipe volumes
	docker compose down -v

demo:  ## Run a scripted demo against the running API
	bash scripts/demo.sh

seed:  ## Seed the sample_data directory with demo log files
	bash scripts/seed_sample_data.sh
