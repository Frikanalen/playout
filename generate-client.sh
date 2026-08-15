#!/usr/bin/env bash
set -euo pipefail

SCHEMA="${1:-schema.yaml}"

uv run --group dev openapi-python-client generate \
  --path "$SCHEMA" \
  --output-path frikanalen_django_api_client \
  --overwrite \
  --meta uv \
  --fail-on-warning
