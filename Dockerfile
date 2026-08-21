FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1

# Install dependencies to system Python (no venv overhead)
ENV UV_PROJECT_ENVIRONMENT=/usr/local

# Copy dependency files
COPY pyproject.toml .python-version uv.lock README.md ./

# Install project and dependencies with cache mounting
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# Copy application code after dependencies are installed
COPY . .

# Install the project itself to make local packages available
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system .

# Runtime stage
FROM python:3.11-slim

# Copy Python packages and app from builder
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app

WORKDIR /app

CMD ["python", "main.py"]
