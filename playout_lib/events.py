"""Django's playout event stream: a nudge to fetch the schedule again.

/api/playout/events is a server-sent event stream. Every event on it, be it
`hello` on connect, `resync` or `schedule.changed`, means the schedule may
differ from what was last loaded, so each one simply asks for a reload. The
scheduler's own poll covers whatever is lost while the stream is down.
"""

import asyncio
from collections.abc import Callable
from urllib.parse import urljoin

import httpx
from loguru import logger

RECONNECT_SECONDS = 5.0
# The server sends a heartbeat every 15 seconds, so a read this long without
# one means the connection is dead even if TCP has not noticed.
READ_TIMEOUT = 45.0


async def listen_for_changes(
    api_url: str, changed: Callable[[], None], transport: httpx.AsyncBaseTransport | None = None
) -> None:
    url = urljoin(api_url, "api/playout/events")
    timeout = httpx.Timeout(10.0, read=READ_TIMEOUT)
    while True:
        try:
            async with (
                httpx.AsyncClient(timeout=timeout, transport=transport) as client,
                client.stream("GET", url, headers={"Accept": "text/event-stream"}) as response,
            ):
                response.raise_for_status()
                logger.info(f"Listening for schedule changes on {url}")
                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        logger.debug(f"Playout event: {line[6:].strip()}")
                        changed()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Playout event stream unavailable ({e!r}); relying on polling")
        await asyncio.sleep(RECONNECT_SECONDS)
