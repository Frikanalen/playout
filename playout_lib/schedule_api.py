import datetime

from loguru import logger

from frikanalen_django_api_client import Client
from frikanalen_django_api_client.api.scheduleitems import scheduleitems_list
from frikanalen_django_api_client.models import ScheduleitemRead
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
            response = await scheduleitems_list.asyncio_detailed(
                client=self.client,  # type: ignore
                date=date_param,
                days=days,
                limit=limit,
                offset=offset,
                surrounding=surrounding,
                # Members' text posters, which the public schedule leaves out.
                include_posters=True,
            )

            logger.debug(f"Response status: {response.status_code}")

            # Extract the URL from the response

            failure = None
            if response.status_code != 200:
                failure = f"HTTP {response.status_code} fetching schedule at offset {offset}"
            elif response.parsed is None:
                failure = f"Failed to parse the schedule at offset {offset}"
                logger.debug(
                    f"Response content: {response.content[:500] if response.content else 'None'}"
                )
            if failure:
                # Without the first page we know nothing, and an empty list
                # would mean "nothing is scheduled": graphics all day.
                if offset == 0:
                    raise RuntimeError(failure)
                logger.error(f"{failure}, keeping the {len(all_items)} items fetched so far")
                break

            paginated_result = response.parsed
            batch_size = len(paginated_result.results)
            all_items.extend(paginated_result.results)
            logger.debug(
                f"Retrieved {batch_size} items (total: {len(all_items)}/{paginated_result.count})"
            )

            # Check if there are more results
            if paginated_result.next_ is None or not paginated_result.next_:
                logger.debug("No more pages to fetch")
                break

            offset += limit

        # Nothing scheduled is a real answer since the jukebox stopped filling
        # every gap: playout shows graphics for the whole stretch.
        if not all_items:
            logger.warning(f"Nothing is scheduled around {date_str}")
        logger.info(f"Successfully fetched {len(all_items)} schedule items for {date_str}")
        return all_items
