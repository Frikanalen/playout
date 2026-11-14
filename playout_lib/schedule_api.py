import datetime

import httpx
from loguru import logger

from frikanalen_django_api_client import Client
from frikanalen_django_api_client.api.scheduleitems import scheduleitems_list
from frikanalen_django_api_client.models import (
    ScheduleitemLiveSource,
    ScheduleitemRead,
    ScheduleitemVideo,
    VideoFileVariantEnum,
)
from frikanalen_django_api_client.types import UNSET


class ScheduleFetcher:
    """Fetches schedule items from the Frikanalen API with pagination support."""

    def __init__(self, client: Client):
        """
        Initialize the schedule fetcher.

        Args:
            client: Authenticated or unauthenticated Frikanalen API client
        """
        self.client = client

    async def get_schedule(
        self,
        date: str | None = None,
        days: int = 1,
        surrounding: bool = False,
    ) -> list[ScheduleitemRead]:
        """
        Fetch schedule items for a specific date with automatic pagination handling.

        Args:
            date: Date in YYYY-MM-DD format or 'today'. Defaults to today if None.
            days: Number of days to fetch. Defaults to 1.
            surrounding: Include events before and after the window. Defaults to False.

        Returns:
            Complete list of ScheduleitemRead objects for the requested period
        """
        date_str = date or "today"
        logger.info(f"Fetching schedule for {date_str} (days={days}, surrounding={surrounding})")
        # The endpoint accepts the literal 'today', but the schema types the
        # parameter as a date, so the generated client calls .isoformat() on
        # whatever it is handed. Omitting it entirely selects today (in
        # Europe/Oslo, per the API) without smuggling a string past the type.
        date_param = UNSET if date_str == "today" else datetime.date.fromisoformat(date_str)
        all_items: list[ScheduleitemRead] = []
        offset = 0
        limit = 100

        while True:
            logger.debug(f"Fetching batch: offset={offset}, limit={limit}")
            failure = None
            page = None
            # Fetched and parsed by hand rather than through
            # scheduleitems_list.asyncio_detailed: the generated parser takes
            # the page as a whole, so one item it can't read (a file variant
            # newer than our pinned schema, say) would sink the whole schedule.
            # Here such an item is dropped and the rest still plays.
            kwargs = scheduleitems_list._get_kwargs(
                date=date_param, days=days, limit=limit, offset=offset, surrounding=surrounding
            )
            try:
                response = await self.client.get_async_httpx_client().request(**kwargs)
            except httpx.HTTPError as error:
                failure = f"{error!r} fetching schedule at offset {offset}"
            else:
                logger.debug(f"Response status: {response.status_code}")
                if response.status_code != 200:
                    failure = f"HTTP {response.status_code} fetching schedule at offset {offset}"
                else:
                    try:
                        page = response.json()
                        results = page["results"]
                        if not isinstance(results, list):
                            raise TypeError("results is not a list")
                    except (ValueError, KeyError, TypeError) as error:
                        failure = f"Failed to parse the schedule at offset {offset} ({error!r})"
                        logger.debug(f"Response content: {response.content[:500]!r}")
            if failure:
                # Without the first page we know nothing, and an empty list
                # would mean "nothing is scheduled": graphics all day.
                if offset == 0:
                    raise RuntimeError(failure)
                logger.error(f"{failure}, keeping the {len(all_items)} items fetched so far")
                break

            for raw in results:
                item = parse_item(raw)
                if item is not None:
                    all_items.append(item)
            logger.debug(f"Retrieved {len(results)} items (total: {len(all_items)})")

            # Check if there are more results
            if not page.get("next"):
                logger.debug("No more pages to fetch")
                break

            offset += limit

        # Nothing scheduled is a real answer since the jukebox stopped filling
        # every gap: playout shows graphics for the whole stretch.
        if not all_items:
            logger.warning(f"Nothing is scheduled around {date_str}")
        logger.info(f"Successfully fetched {len(all_items)} schedule items for {date_str}")
        return all_items


KNOWN_VARIANTS = {variant.value for variant in VideoFileVariantEnum}


def parse_item(raw) -> ScheduleitemRead | None:
    """One schedule item from the API, or None if playout can't read it.

    A dropped item leaves a gap, which gets the gap graphic. The error names
    the item so it can be found and fixed; Loki alerts on it (see the infra
    repo's roles/loki/files/playout-rules.yml).
    """
    item_id = raw.get("id") if isinstance(raw, dict) else None
    try:
        raw = _without_unknown_variants(raw)
        item = ScheduleitemRead.from_dict(raw)
        # The generated parser hands back the raw dict, not an error, when a
        # nullable nested object fails to parse.
        if item.video is not None and not isinstance(item.video, ScheduleitemVideo):
            raise ValueError(f"unreadable video {item.video!r}")
        if item.live_source is not None and not isinstance(
            item.live_source, ScheduleitemLiveSource
        ):
            raise ValueError(f"unreadable live source {item.live_source!r}")
        return item
    except Exception as error:
        start = raw.get("starttime") if isinstance(raw, dict) else None
        logger.error(f"Skipping schedule item {item_id} at {start}, can't read it: {error!r}")
        return None


def _without_unknown_variants(raw):
    """raw minus video files of variants newer than our pinned schema.

    Playout plays files it looks up separately, so a schedule item's file
    list is information only, and a variant it doesn't know is no reason to
    drop the programme. This is what kept everything new off air on
    2026-11-14, when the API started listing HLS files.
    """
    video = raw.get("video")
    if not isinstance(video, dict) or not isinstance(video.get("files"), list):
        return raw
    files = [
        f for f in video["files"] if not isinstance(f, dict) or f.get("variant") in KNOWN_VARIANTS
    ]
    if len(files) == len(video["files"]):
        return raw
    unknown = sorted({f.get("variant") for f in video["files"] if f not in files})
    logger.warning(
        f"Schedule item {raw.get('id')} lists file variants playout doesn't know: {unknown}"
    )
    return {**raw, "video": {**video, "files": files}}
