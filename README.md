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

### Schedule changes

Playout follows the schedule as it changes. It listens to Django's event
stream at `/api/playout/events` and reloads the schedule whenever an event
arrives, every 15 minutes in case the stream is down, and just after midnight to pick
up the next day. Each load is reconciled
against the running tasks: an unchanged booking keeps playing, a new one is
added, and one that moved or was removed is cancelled. The item on air is kept
and only its end time moves, unless it was replaced by something else.

### Live transmissions

A schedule item with a `liveTransmission` plays its MediaMTX source,
`contrib/live/<stream UUID>`, instead of a video file. CasparCG reads it from
`LIVE_INPUT_URL` (for example `rtsp://192.0.2.10:8554`), so that address must
be reachable from the CasparCG host, not just from the playout pod.

MediaMTX checks every read with Django. Issue one **Playout reader (all
enabled sources)** credential in the Django admin, with no source, and give it
to playout as `LIVE_READER_CREDENTIAL=<key UUID>:<password>`, preferably from
a Secret via the chart's `envFrom`. It reads any enabled source, so new sources
need no playout change.

The source plays on its own layer above the programme (`LIVE_LAYER`, default
`1-55`), while the filler loops on the programme layer for the whole slot.
CasparCG (2.5) answers `PLAY` of a dead RTSP source with `202 PLAY OK` and
plays black, so playout never trusts the reply: it starts the source 15
seconds before the slot with the live layer's opacity and volume at 0, and
shows it (opacity 1, filler muted) only while `INFO` shows the source's clock
advancing. A source that is up ahead of time is on air at the start time.
`LOADBG` is no use here: a background producer shows nothing in `INFO`, live
or dead.

Once on air, CasparCG is no help: after an encoder drop its clock in `INFO`
keeps running, although the input is dead and never reconnects. So playout
watches MediaMTX's Prometheus metrics at `LIVE_METRICS_URL` (for example
`http://mediamtx-metrics:9998/metrics`) every 2 seconds. When no RTSP reader
of the path is getting more bytes for two checks in a row, it hides the live
layer again, so the filler underneath is on air, waits until the path has a publisher again (`paths{state="ready"}`) and
restarts the source hidden, until the slot ends. An unreachable metrics endpoint leaves the
source on air. Without `LIVE_METRICS_URL` it falls back to the `INFO` clock,
which only notices a producer that ends. Without `LIVE_INPUT_URL` the whole
slot is covered with filler. The password is redacted from the command log.

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
  - `events.py` - Django's playout event stream
  - `items.py` - Playout items
  - `logging_setup.py` - Logging configuration
  - `loudness.py` - Playback gain from R128 measurements
  - `scheduler.py` - Scheduling logic
