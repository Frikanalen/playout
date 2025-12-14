"""Schedule item classes for different types of playout content."""

import asyncio
from datetime import datetime

import pytz
from loguru import logger


def localtime():
    """Get current time in Oslo timezone."""
    return datetime.now(tz=pytz.timezone("Europe/Oslo"))


class Item:
    """Base class for all playable items."""

    def __init__(self, layer):
        self.layer = layer
        self.prepare = None

    async def stop(self):
        """Stop playback on this item's layer."""
        from .caspar_player import current_player

        await current_player.issue(f"STOP {self.layer}")

    async def clear(self):
        """Clear this item's layer."""
        from .caspar_player import current_player

        await current_player.issue(f"CLEAR {self.layer}")

    def __repr__(self) -> str:
        return "[Item]"


class PlannedItem(Item):
    """Base class for scheduled items with start and end times."""

    def __init__(self, layer, start_time, end_time):
        self.start_time = start_time
        self.end_time = end_time
        super().__init__(layer)

    async def sleep_until_time_to_prepare(self):
        """Sleep until 5 seconds before scheduled start time."""
        seconds_until_start = (self.start_time - localtime()).total_seconds()
        logger.debug(f"{seconds_until_start} seconds until start.")
        await asyncio.sleep(seconds_until_start - 5)

    async def sleep_until_time_to_play(self):
        """Sleep until scheduled start time."""
        seconds_until_start = (self.start_time - localtime()).total_seconds()
        logger.debug(f"{seconds_until_start} seconds until play. {repr(self)}")
        await asyncio.sleep(seconds_until_start)

    def already_done(self):
        """Check if this item's scheduled time has passed."""
        return localtime() > self.end_time

    def _seconds_left(self):
        """Calculate remaining seconds until scheduled end."""
        return (self.end_time - localtime()).total_seconds()

    async def _completion(self):
        """Block until the scheduled end time or until cancelled."""
        logger.info(f"waiting for completion {self._seconds_left()} seconds left {repr(self)}")
        await asyncio.sleep(self._seconds_left())
        logger.info(f"Finished waiting {repr(self)}")


class Graphic(PlannedItem):
    """A scheduled graphic/image overlay to be displayed."""

    def __init__(self, url, layer, start_time, end_time):
        super().__init__(layer, start_time, end_time)
        self.has_been_prepared = False
        self.url = url

    async def cue(self):
        """Start displaying the graphic."""
        from .caspar_player import current_player

        try:
            if self.has_been_prepared:
                await current_player.issue(f"CG {self.layer}1 PLAY 0")
                await current_player.issue(f"PLAY {self.layer} filler/FrikanalenLoop loop 0")
            else:
                await current_player.issue(f'CG {self.layer}1 ADD 0 "{self.url}" 1')
                await current_player.issue(f"PLAY {self.layer}")

            # If we have time for it, do a nice and steady fade to black
            # two seconds before the next programme, just like the old
            # NRK clock used to do it! ^_^
            if self._seconds_left() >= 5.0:
                await asyncio.sleep(self._seconds_left() - 2.0)
                await current_player.issue(f"MIXER {self.layer}1 OPACITY 0 50 easeinsine")
                await current_player.issue(f"MIXER {self.layer} OPACITY 0 50 easeinsine")

            await self._completion()
            await self.clear()
            await current_player.issue(f"MIXER {self.layer}1 CLEAR")
            await current_player.issue(f"MIXER {self.layer} CLEAR")

        except asyncio.CancelledError:
            await self.clear()

    async def clear(self):
        """Clear the graphic and reset mixer settings."""
        from .caspar_player import current_player

        await current_player.issue(f"CLEAR {self.layer}")
        await current_player.issue(f"CG {self.layer}1 CLEAR")
        await current_player.issue(f"MIXER {self.layer}1 CLEAR")
        await current_player.issue(f"MIXER {self.layer} CLEAR")

    async def prepare(self):
        """Preload the graphic into CasparCG."""
        from .caspar_player import current_player

        try:
            await current_player.issue(f'CG {self.layer}1 ADD 0 "{self.url}" 0')
            await current_player.issue(f"LOADBG {self.layer} filler/FrikanalenLoop loop 0")
            self.has_been_prepared = True
        except asyncio.CancelledError:
            pass

    def __repr__(self):
        time_range = f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
        duration = (self.end_time - self.start_time).total_seconds()
        return f"[{time_range} Graphic: {duration:.1f}s]"
