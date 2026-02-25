FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY backend/pyproject.toml backend/uv.lock ./

# Install production dependencies only (no dev group)
RUN uv sync --frozen --no-dev

# Copy application source and frontend
COPY backend/src/ ./src/
COPY frontend/ ../frontend/

# Expose the API port
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
