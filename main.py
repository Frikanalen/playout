#!/usr/bin/env python3
"""Main entry point for the Frikanalen playout system."""

import asyncio
import signal

from playout_lib.caspar_player import current_player

from playout_lib.config import CASPAR_HOST
from playout_lib.logging_setup import logger
from playout_lib.scheduler import Scheduler


class Playout:
    """Main playout application coordinator."""

    async def run(self):
        """Initialize and run the playout system."""
        scheduler = Scheduler()
        await current_player.connect()
        await scheduler.run()


def main():
    """Entry point for the playout application."""
    logger.info(f"Playout starting, connecting to {CASPAR_HOST}...")
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGTERM, loop.stop)
    loop.add_signal_handler(signal.SIGINT, loop.stop)
    result = loop.run_until_complete(Playout().run())
    print(result)


if __name__ == "__main__":
    main()
