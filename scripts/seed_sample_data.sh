#!/usr/bin/env bash
# Seed sample_data/ with a representative log file for demos.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$DIR/sample_data"
mkdir -p "$OUT"

cat > "$OUT/sample.log" <<'EOF'
2026-04-19 12:00:01 INFO  Server started on port 8080
2026-04-19 12:00:05 INFO  Listening for connections
2026-04-19 12:01:22 WARN  Slow query detected: 1230ms
2026-04-19 12:02:45 INFO  Request /api/v1/users OK
2026-04-19 12:03:11 ERROR Database connection refused
2026-04-19 12:03:12 ERROR Retrying in 5s...
2026-04-19 12:03:17 INFO  Reconnected to database
2026-04-19 12:04:00 WARN  Deprecated endpoint /v0/metrics
2026-04-19 12:05:33 ERROR Unhandled exception in worker:
2026-04-19 12:05:33 ERROR Traceback (most recent call last):
2026-04-19 12:05:33 ERROR   File "worker.py", line 42, in run
2026-04-19 12:05:33 ERROR ValueError: bad payload
2026-04-19 12:06:00 INFO  Scheduled job completed
2026-04-19 12:07:15 FATAL Out of memory — restarting
EOF

echo "Seeded $OUT/sample.log"
