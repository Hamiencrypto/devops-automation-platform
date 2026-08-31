FROM python:3.11-slim AS base

# ---------------------------------------------------------------------
# System dependencies
# ---------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
      gcc \
      libpq-dev \
      && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ---------------------------------------------------------------------
# Python dependencies — cached layer
# ---------------------------------------------------------------------
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# ---------------------------------------------------------------------
# Application source
# ---------------------------------------------------------------------
COPY . .

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
  CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
