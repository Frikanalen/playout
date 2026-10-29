"""Live transmissions: play a MediaMTX contribution at its booked time."""

import asyncio
import re
from dataclasses import dataclass, field
from urllib.parse import quote, urlsplit, urlunsplit
from xml.etree import ElementTree

import httpx
from loguru import logger

from playout_lib.config import (
    LIVE_INPUT_URL,
    LIVE_METRICS_URL,
    LIVE_PROBE_LAYER,
    LIVE_READER_CREDENTIAL,
)
from playout_lib.items import PlannedItem

FILLER = "filler/FrikanalenLoop"

# How long to wait before trying again when the source is not (yet)
# publishing. An encoder that comes up a little late still gets on air.
RETRY_INTERVAL = 10.0

# CasparCG answers PLAY of a dead RTSP source with 202 OK and plays black,
# so the only sign of a working input is its clock advancing in INFO. A
# healthy source takes about 4 seconds to connect and shows picture then.
STARTUP_TIME = 12.0
# How often the probe layer is checked while the source starts.
PROBE_INTERVAL = 1.0
# How often to check that the source on air is still flowing.
WATCH_INTERVAL = 2.0
# Checks in a row a source may look dead before the filler goes back. One
# missed check rides out a slow metrics scrape.
STALL_CHECKS = 2

_SAMPLE = re.compile(r"^(\w+)(?:\{(.*)\})?\s+(\S+)")
_LABEL = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')


@dataclass
class PathState:
    """What MediaMTX's metrics say about one path."""

    # Whether a publisher is connected and sending.
    ready: bool = False
    # Bytes sent so far to each RTSP reader of the path, by session id.
    readers: dict[str, float] = field(default_factory=dict)


def path_state(metrics: str, path: str) -> PathState:
    """Read the state of path from MediaMTX's Prometheus text output."""
    state = PathState()
    for line in metrics.splitlines():
        match = _SAMPLE.match(line)
        if not match:
            continue
        name, labels, value = match.groups()
        labels = dict(_LABEL.findall(labels or ""))
        try:
            value = float(value)
        except ValueError:
            continue
        if name == "paths" and labels.get("name") == path and labels.get("state") == "ready":
            state.ready = value > 0
        elif (
            name == "rtsp_sessions_outbound_bytes"
            and labels.get("path") == path
            and labels.get("state") == "read"
        ):
            state.readers[labels.get("id", "")] = value
    return state


async def read_path_state(path: str) -> PathState | None:
    """The state of path from MediaMTX, or None when it cannot be read."""
    try:
        async with httpx.AsyncClient(timeout=WATCH_INTERVAL) as client:
            response = await client.get(LIVE_METRICS_URL)
            response.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning(f"Cannot read MediaMTX metrics: {e}")
        return None
    return path_state(response.text, path)


def still_flowing(before: PathState | None, now: PathState) -> bool:
    """Whether a reader of the path got more data since the previous check.

    MediaMTX drops every reader of a path within a couple of seconds of its
    publisher going away, and a reader whose byte count stops is fed nothing.
    """
    if not now.readers:
        return False
    if before is None:
        return True
    return any(now.readers[i] > before.readers[i] for i in now.readers.keys() & before.readers)


def foreground_time(info, layer) -> float | None:
    """The playing position of the ffmpeg producer on layer, from INFO XML.

    None when the layer is empty, still connecting (CasparCG wraps it in a
    transition producer) or carries no position at all.
    """
    if not isinstance(info, str):
        return None
    try:
        root = ElementTree.fromstring(info.strip())
    except ElementTree.ParseError:
        return None
    # INFO <channel-layer> returns the whole channel in CasparCG 2.5.
    foreground = root.find(f"./stage/layer/layer_{layer.split('-')[1]}/foreground")
    if foreground is None or foreground.findtext("producer") != "ffmpeg":
        return None
    position = foreground.findtext("file/time")
    try:
        return float(position) if position is not None else None
    except ValueError:
        return None


class LiveTransmission(PlannedItem):
    """A scheduled live input, read from MediaMTX's contrib/live/<UUID> path."""

    def __init__(self, stream_id, layer, start_time, end_time):
        super().__init__(layer, start_time, end_time)
        self.stream_id = str(stream_id)

    @property
    def path(self) -> str:
        return f"contrib/live/{self.stream_id}"

    def _url(self, redact=False) -> str | None:
        """The URL CasparCG reads the source from, with the reader's credentials.

        MediaMTX authenticates every read against Django. Playout's reader
        credential covers every enabled source, so the path alone picks it.
        """
        if not LIVE_INPUT_URL:
            return None
        parts = urlsplit(f"{LIVE_INPUT_URL.rstrip('/')}/{self.path}")
        if LIVE_READER_CREDENTIAL:
            username, _, password = LIVE_READER_CREDENTIAL.partition(":")
            if redact:
                password = "***"
            netloc = f"{quote(username, safe='')}:{quote(password, safe='')}@{parts.netloc}"
            parts = parts._replace(netloc=netloc)
        else:
            logger.warning("LIVE_READER_CREDENTIAL is not set; MediaMTX will refuse the read")
        return urlunsplit(parts)

    async def _play_live(self, layer):
        from .caspar_player import current_player

        await current_player.issue(
            f'PLAY {layer} "{self._url()}" "-filter:a aformat=sample_rates=48000"',
            log_as=f"PLAY {layer} {self._url(redact=True)}",
        )

    async def _position(self, layer) -> float | None:
        from .caspar_player import current_player

        return foreground_time(await current_player.issue(f"INFO {layer}"), layer)

    async def _advancing(self, layer, since: float | None) -> tuple[bool, float | None]:
        """Whether layer's source has moved on from position since."""
        position = await self._position(layer)
        return position is not None and since is not None and position > since, position

    async def _sleep(self, seconds):
        await asyncio.sleep(max(0.0, min(seconds, self._seconds_left())))

    async def _bring_up(self) -> bool:
        """Start the source on the hidden probe layer and cut to it once it flows.

        The probe sits below the programme layer and is muted, so a source that
        never comes up costs nothing on air. SWAP moves the already-running
        producer, so the cut shows no black while it reconnects.
        """
        from .caspar_player import current_player

        await current_player.issue(f"MIXER {LIVE_PROBE_LAYER} VOLUME 0")
        await self._play_live(LIVE_PROBE_LAYER)
        flowing, position = False, None
        waited = 0.0
        while not flowing and waited < STARTUP_TIME and self._seconds_left() > 0:
            await self._sleep(PROBE_INTERVAL)
            waited += PROBE_INTERVAL
            flowing, position = await self._advancing(LIVE_PROBE_LAYER, position)
        if flowing:
            await current_player.issue(f"SWAP {LIVE_PROBE_LAYER} {self.layer}")
        await current_player.issue(f"CLEAR {LIVE_PROBE_LAYER}")
        return flowing

    async def cue(self):
        """Keep the live source on air for the slot, covering with filler when it is not."""
        from .caspar_player import current_player

        try:
            # The previous video's loudness gain sticks to the layer. The
            # contribution is not measured, so play it at its own level.
            await current_player.issue(f"MIXER {self.layer} VOLUME 1.0000")
            await current_player.issue(f"PLAY {self.layer} {FILLER} loop 0")

            if self._url() is None:
                logger.error("LIVE_INPUT_URL is not set; covering live slot with filler")
                await self._completion()
            else:
                await self._keep_on_air()

            await current_player.issue(f"STOP {self.layer}")
        except asyncio.CancelledError:
            logger.warning("asyncio.CancelledError during live transmission")
        except Exception:
            # Never leave the slot to whatever the layers happened to hold.
            logger.exception(f"Live transmission {self.stream_id} failed; covering with filler")
            try:
                await current_player.issue(f"CLEAR {LIVE_PROBE_LAYER}")
                await current_player.issue(f"PLAY {self.layer} {FILLER} loop 0")
                await self._completion()
                await current_player.issue(f"STOP {self.layer}")
            except Exception:
                logger.exception("Could not cover the failed live transmission")

    async def _wait_for_publisher(self):
        """Wait until MediaMTX has a publisher on the path, so a retry is quick."""
        if not LIVE_METRICS_URL:
            await self._sleep(RETRY_INTERVAL)
            return
        while self._seconds_left() > STARTUP_TIME:
            state = await read_path_state(self.path)
            if state is None or state.ready:
                return
            await self._sleep(WATCH_INTERVAL)

    async def _watch(self):
        """Return when the source on air stops flowing or the slot ends.

        Returns True for a stall. CasparCG's own clock keeps running on a dead
        input, so MediaMTX's metrics are the signal when they are configured.
        """
        if not LIVE_METRICS_URL:
            logger.warning("LIVE_METRICS_URL is not set; an encoder drop will not be noticed")
        before, misses = None, 0
        position = await self._position(self.layer)
        while True:
            await self._sleep(WATCH_INTERVAL)
            if self._seconds_left() <= 0:
                return False
            if LIVE_METRICS_URL:
                state = await read_path_state(self.path)
                if state is None:
                    # MediaMTX unreachable says nothing about the source.
                    continue
                flowing, before = still_flowing(before, state), state
            else:
                flowing, position = await self._advancing(self.layer, position)
            misses = 0 if flowing else misses + 1
            if misses >= STALL_CHECKS:
                return True

    async def _keep_on_air(self):
        from .caspar_player import current_player

        while self._seconds_left() > STARTUP_TIME:
            logger.info(f"Taking live source {self._url(redact=True)}")
            if not await self._bring_up():
                logger.error(f"Live source {self.stream_id} is not flowing; filler stays on air")
                await self._wait_for_publisher()
                continue

            logger.info(f"Live source {self.stream_id} is on air")
            if not await self._watch():
                break
            # The encoder dropped or froze: never leave black on air.
            logger.error(f"Live source {self.stream_id} stalled; back to filler")
            await current_player.issue(f"PLAY {self.layer} {FILLER} loop 0")
            await self._wait_for_publisher()
        await self._completion()

    def __repr__(self):
        time_range = f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
        return f"[{time_range} Live: {self.stream_id}]"
