FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

WORKDIR /app

# Enable bytecode compilation for faster startup
ENV UV_COMPILE_BYTECODE=1

# Install dependencies to system Python (no venv overhead)
ENV UV_PROJECT_ENVIRONMENT=/usr/local

# We need git for retrieving dependencies
RUN apt update && apt install -y git && apt clean && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml .python-version uv.lock README.md ./

# Install project and dependencies with cache mounting
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable && \
    uv pip install --system --no-cache "git+https://github.com/frikanalen/frikanalen-python-client.git@main"

# Copy application code after dependencies are installed
COPY . .

# Runtime stage
FROM python:3.11-slim

# Copy Python packages and app from builder
COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app

WORKDIR /app

CMD ["python", "main.py"]
