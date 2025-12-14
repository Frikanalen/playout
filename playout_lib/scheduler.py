"""Schedule management and item playback coordination."""

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta

from loguru import logger

from .api import load_schedule
from .config import API_URL
from .items import localtime


class ScheduleExpiryException(Exception):
    """Raised when the current schedule has expired and needs refresh."""

    pass


class Scheduler:
    """Manages loading, validation, and execution of the playout schedule."""

    schedule_refresh_rate = timedelta(seconds=30)

    def __init__(self):
        self.schedule = []
        self.last_refreshed = datetime.min

    async def _play_item(self, item):
        """Execute a scheduled item with preparation and timing.

        Args:
            item: The schedule item to play

        Raises:
            ScheduleExpiryException: If schedule needs refresh
        """
        prepare_op = getattr(item, "prepare", None)
        if callable(prepare_op):
            await item.sleep_until_time_to_prepare()
            await self._prepare_item(item)

        await item.sleep_until_time_to_play()
        logger.info("Playing item")
        await item.cue()

        if self.last_refreshed + self.schedule_refresh_rate > localtime():
            raise ScheduleExpiryException

    async def _prepare_item(self, item):
        """Perform preparatory work for an item before playback."""
        prepare_op: Callable | None = getattr(item, "prepare", None)

        if not callable(prepare_op):
            logger.info(f"Next item {item} does not have a prepare() method")
            return

        logger.info("Preparing next item")
        await prepare_op()

    async def _validate(self):
        """Validate the loaded schedule (placeholder for future validation)."""
        pass

    async def run(self):
        """Main scheduler loop - loads schedule and executes items."""
        while True:
            tasks = ()
            try:
                self.schedule = await load_schedule(API_URL)
                self.last_refreshed = localtime()
            except Exception:
                logger.error("Failed to load a schedule!")
                raise

            try:
                await self._validate()
            except Exception:
                logger.error("Failed to validate schedule!")
                raise

            for item in self.schedule:
                if not item.already_done():
                    tasks = tasks + (await self.task_from_item(item),)
                else:
                    logger.debug(f"ScheduleItem {item} is in the past, skipping...")

            logger.info("Waiting for tasks...")
            await asyncio.wait(tasks)

    async def task_from_item(self, item):
        """Create an asyncio task for a schedule item.

        Args:
            item: The schedule item to create a task for

        Returns:
            asyncio.Task: The created task
        """
        logger.info(f"Adding cue to task list: {item}")
        task = asyncio.create_task(self._play_item(item))
        return task
