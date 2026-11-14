#!/usr/bin/env python3
"""Main entry point for the Frikanalen playout system."""

import asyncio
import os
import signal
import sys

from loguru import logger

from playout_lib.caspar_player import current_player
from playout_lib.config import CASPAR_HOST
from playout_lib.scheduler import Scheduler

# Configure loguru for the playout system
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    colorize=True,
    level="DEBUG",
)


class Playout:
    """Main playout application coordinator."""

    async def run(self):
        """Initialize and run the playout system.

        Returns only if the connection to CasparCG is lost. CasparCG comes
        back empty after a crash, so the way back on air is to start over:
        main() replaces this process with a fresh playout, which waits for
        CasparCG and cues whatever should be on air by now, joining videos at
        the right point. That is what restarting playout by hand did on
        2026-11-14, only seconds after the crash rather than minutes.
        """
        scheduler = Scheduler()
        await current_player.connect()
        playing = asyncio.create_task(scheduler.run())
        lost = asyncio.create_task(current_player.connection_lost.wait())
        await asyncio.wait({playing, lost}, return_when=asyncio.FIRST_COMPLETED)
        if playing.done():
            # The scheduler never returns on its own; surface why it did.
            lost.cancel()
            playing.result()
            raise RuntimeError("The scheduler stopped")
        playing.cancel()


def main():
    """Entry point for the playout application."""
    logger.info(f"Playout starting, connecting to {CASPAR_HOST}...")
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGTERM, loop.stop)
    loop.add_signal_handler(signal.SIGINT, loop.stop)
    loop.run_until_complete(Playout().run())
    logger.error("Lost CasparCG, restarting playout to cue what should be on air")
    # Exec rather than exit: Kubernetes would restart the container too, but
    # after a crash-loop back-off of up to minutes if CasparCG fails twice.
    os.execv(sys.executable, [sys.executable, *sys.argv])


if __name__ == "__main__":
    main()
