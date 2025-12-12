# Frikanalen Playout System

A modern Python application for managing playout integration with CasparCG.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

Install dependencies using uv:

```bash
uv sync
```

## Development

### Running the application

```bash
uv run playout
```

### Running tests

```bash
uv run pytest
```

### Code formatting and linting

This project uses Ruff for code formatting and linting:

```bash
# Format code
uv run ruff format .

# Run linter
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check --fix .
```

### Adding dependencies

```bash
# Add a runtime dependency
uv add <package-name>

# Add a development dependency
uv add --dev <package-name>
```

## Docker

Build and run using Docker:

```bash
docker build -t frikanalen-playout .
docker run frikanalen-playout
```

## Project Structure

- `main.py` - Application entry point
- `playout_lib/` - Core application modules
  - `api.py` - API integration
  - `caspar_player.py` - CasparCG player interface
  - `config.py` - Configuration management
  - `items.py` - Playout items
  - `logging_setup.py` - Logging configuration
  - `scheduler.py` - Scheduling logic
