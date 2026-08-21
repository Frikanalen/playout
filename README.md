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

The schedule API and interstitial graphics endpoint can be configured
independently with `API_URL` and `GRAPHICS_URL`. For example, a staging
deployment should set `GRAPHICS_URL=https://staging.frikanalen.no/graphics/`.

### Refreshing the API schema and regenerating the client

The repo keeps a checked-in OpenAPI snapshot in `schema.yaml`. Two scripts manage schema updates and client generation:

**Fetch the latest schema from the backend:**
```bash
./update-schema.sh
```

This fetches the current schema from `http://localhost:8000/api/schema` and overwrites `schema.yaml`. The backend must be running locally.

**Regenerate the Python client from the schema:**
```bash
./generate-client.sh
```

This runs `openapi-python-client` to generate the Python client code from `schema.yaml` into `frikanalen_django_api_client/`.

For local development, run both scripts in sequence. CI only runs `generate-client.sh` to ensure the client matches the committed schema.

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

## Loudness normalization

Video files carry an integrated loudness and a true peak measured by the upload
pipeline (`integratedLufs` and `truepeakLufs` on the video file record). When
the file about to go to air has been measured, playout sets the CasparCG layer
volume so it comes out at the house target instead of at its delivered level.
Files that have not been measured play unchanged, and a failed lookup never
holds up playout.

Nothing downstream of playout limits, so the true peak ceiling is enforced as a
hard constraint in both directions: a file measured above it is turned down to
it, and a quiet file with hot peaks is lifted only as far as its headroom
allows, staying under target rather than clipping. Roughly half the library
peaks above -1 dBTP as delivered, though most of those are loud enough that
loudness alone already turns them down further than the ceiling would.

Two limits are worth knowing. Measurements outside a plausible range are
ignored rather than obeyed -- a few records read +80 dBTP or +5 LUFS, and
acting on those literally would mute the programme. And a file with no usable
true peak is never boosted, only ever turned down: without a peak we cannot
rule out that it already sits at full scale. That means playout will not push
anything over 0 dBFS, but it cannot make a delivered file that is already over
into one that is not.

| Variable | Default | Meaning |
| --- | --- | --- |
| `LOUDNESS_NORMALIZATION` | `true` | Set false to play everything at its delivered level. |
| `LOUDNESS_TARGET_LUFS` | `-23.0` | House target loudness (EBU R128). |
| `LOUDNESS_MAX_BOOST_DB` | `12.0` | Ceiling on how far a quiet file may be lifted. |
| `LOUDNESS_TRUEPEAK_CEILING_DBTP` | `-1.0` | Boost stops here rather than clipping. |

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
  - `loudness.py` - Playback gain from R128 measurements
  - `scheduler.py` - Scheduling logic
