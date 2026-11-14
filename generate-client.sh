#!/usr/bin/env bash
set -euo pipefail

SCHEMA="${1:-schema.yaml}"
OUTPUT="frikanalen_django_api_client"

# Wipe the tree first: --overwrite replaces files it generates, but leaves
# behind anything from an earlier run that the current schema no longer emits.
# Stale modules that only exist locally hide breakage until it reaches CI.
rm -rf "$OUTPUT"

# --custom-template-path: client-templates/ overrides the enum templates so a
# value the API added after our schema was pinned is kept rather than failing
# the whole response (an unknown file variant took everything new off air on
# 2026-11-14).
#
# --meta none emits the package flat at --output-path, which is what
# [tool.hatch.build.targets.wheel] packages expects. The client's runtime
# dependencies (httpx, attrs) are declared in our own pyproject.toml, since
# no client-local pyproject.toml is generated or installed.
uv run --group dev openapi-python-client generate \
  --path "$SCHEMA" \
  --output-path "$OUTPUT" \
  --meta none \
  --config openapi-python-client.yaml \
  --custom-template-path client-templates \
  --fail-on-warning

# --meta none skips py.typed, so restore it to keep the installed package typed.
touch "$OUTPUT/py.typed"
