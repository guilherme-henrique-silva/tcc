# Dockerfile - Multi-stage build for backend and frontend
#
# Dependencies are managed with uv (https://docs.astral.sh/uv/).
# Edit the high-level pins in */requirements.in, then regenerate the locked
# */requirements.txt with:  bash scripts/lock.sh
# The build installs strictly from the locked */requirements.txt files.

# Stage 1: Builder - resolves and installs deps into one isolated venv per service
FROM python:3.11-slim AS builder

# Bring in the uv binary from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_HTTP_TIMEOUT=300 \
    UV_NO_CACHE=1

WORKDIR /app

COPY backend/requirements.txt backend-requirements.txt
COPY frontend/requirements.txt frontend-requirements.txt

# Separate venvs so each runtime image carries only the deps it needs
# (the backend pulls torch/docling; the frontend stays lightweight).
RUN uv venv --relocatable /opt/venv-backend \
 && VIRTUAL_ENV=/opt/venv-backend uv pip install -r backend-requirements.txt
RUN uv venv --relocatable /opt/venv-frontend \
 && VIRTUAL_ENV=/opt/venv-frontend uv pip install -r frontend-requirements.txt

# Stage 2: Backend Runtime (FastAPI)
FROM python:3.11-slim AS backend

WORKDIR /app/backend

# Copy the prebuilt backend venv
COPY --from=builder /opt/venv-backend /opt/venv

# Copy source code
COPY backend/ .
COPY backend/src /app/src

# Set environment
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Stage 3: Frontend Runtime (Streamlit)
FROM python:3.11-slim AS frontend

WORKDIR /app/frontend

# Copy the prebuilt frontend venv
COPY --from=builder /opt/venv-frontend /opt/venv

# Copy source code
COPY frontend/ .
COPY backend/src /app/src

# Set environment
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_PORT=8501

EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless", "true"]
