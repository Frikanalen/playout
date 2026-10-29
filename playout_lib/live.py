"""Live transmissions: play a MediaMTX contribution at its booked time."""

import asyncio
from urllib.parse import quote, urlsplit, urlunsplit

from loguru import logger

from playout_lib.config import LIVE_INPUT_URL, LIVE_SOURCE_CREDENTIALS
from playout_lib.items import PlannedItem

FILLER = "filler/FrikanalenLoop"

# How long to wait before trying again when the source is not (yet)
# publishing. An encoder that comes up a little late still gets on air.
RETRY_INTERVAL = 10.0


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

        MediaMTX authenticates every read against Django, and Read credentials
        are scoped to one source, so playout holds one per source it may air.
        """
        if not LIVE_INPUT_URL:
            return None
        parts = urlsplit(f"{LIVE_INPUT_URL.rstrip('/')}/{self.path}")
        if credential := LIVE_SOURCE_CREDENTIALS.get(self.stream_id):
            username, _, password = credential.partition(":")
            if redact:
                password = "***"
            netloc = f"{quote(username, safe='')}:{quote(password, safe='')}@{parts.netloc}"
            parts = parts._replace(netloc=netloc)
        else:
            logger.warning(f"No read credential configured for live source {self.stream_id}")
        return urlunsplit(parts)

    async def _play_live(self) -> bool:
        from .caspar_player import current_player

        url = self._url()
        logger.info(f"Taking live source {self._url(redact=True)}")
        try:
            await current_player.issue(
                f'PLAY {self.layer} "{url}" "-filter:a aformat=sample_rates=48000"'
                " MIX 50 1 LINEAR RIGHT",
                log_as=f"PLAY {self.layer} {self._url(redact=True)}",
            )
        except ValueError as error:
            # CasparCG refuses the PLAY when the source is not publishing.
            logger.error(f"Could not take live source {self.stream_id}: {error}")
            return False
        return True

    async def cue(self):
        """Put the live source on air, covering with filler until it comes up."""
        from .caspar_player import current_player

        try:
            # The previous video's loudness gain sticks to the layer. The
            # contribution is not measured, so play it at its own level.
            await current_player.issue(f"MIXER {self.layer} VOLUME 1.0000")

            if self._url() is None:
                logger.error("LIVE_INPUT_URL is not set; covering live slot with filler")
                await current_player.issue(f"PLAY {self.layer} {FILLER} loop 0")
            else:
                while not await self._play_live():
                    await current_player.issue(f"PLAY {self.layer} {FILLER} loop 0")
                    if self._seconds_left() <= RETRY_INTERVAL:
                        break
                    await asyncio.sleep(RETRY_INTERVAL)

            await self._completion()
            await current_player.issue(f"STOP {self.layer}")
        except asyncio.CancelledError:
            logger.warning("asyncio.CancelledError during live transmission")

    def __repr__(self):
        time_range = f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
        return f"[{time_range} Live: {self.stream_id}]"
