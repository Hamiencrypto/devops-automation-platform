"""Pytest configuration — uses a throw-away SQLite database for tests."""

import os
import sys
from pathlib import Path

# Make `app` importable when running `pytest` from the backend/ folder.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Use in-memory SQLite for tests
os.environ.setdefault(
    "DATABASE_URL", "sqlite:///:memory:"
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-used-anywhere")
os.environ.setdefault("ENABLE_AUTH", "false")
