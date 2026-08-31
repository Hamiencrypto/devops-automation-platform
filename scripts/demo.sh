#!/usr/bin/env bash
# ====================================================================
# Scripted end-to-end demo — fires 10 representative commands at the
# running backend and prints pretty JSON responses.
# ====================================================================
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

run() {
  local cmd="$1"
  local extra="${2:-}"
  echo ""
  echo -e "${CYAN}▶  $cmd${NC}"
  local body
  if [ -n "$extra" ]; then
    body=$(jq -n --arg c "$cmd" --argjson d "$extra" '{command:$c} + $d')
  else
    body=$(jq -n --arg c "$cmd" '{command:$c}')
  fi
  curl -s -X POST "$BASE/execute" \
    -H "Content-Type: application/json" \
    -d "$body" | jq '{task_id, status, intent, summary, duration_ms, warnings}'
}

echo -e "${YELLOW}=== DevOps MCP Platform — Live Demo ===${NC}"
echo -e "${YELLOW}Target: $BASE${NC}"

run "system health"
run "disk usage"
run "memory usage"
run "list all containers"
run "deploy nginx on port 8080" '{"dry_run": true}'
run "count lines in /data/sample.log"
run "analyze logs at /data/sample.log"
run "find errors in /data/sample.log"
run "stop mcp-managed-nginx" '{"confirm_destructive": true, "dry_run": true}'
run "list pods in default namespace"

echo ""
echo -e "${GREEN}✓  Demo complete. Check http://localhost:3000 for the web UI.${NC}"
