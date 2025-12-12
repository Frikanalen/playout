# Use modern Python base image
FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml .python-version ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev

# Copy the application code
COPY . .

# Run the application
CMD ["uv", "run", "playout"]
