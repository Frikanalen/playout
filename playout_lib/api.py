"""API and data fetching functionality for schedule and video files."""

from itertools import pairwise

from frikanalen_django_api_client import Client
from frikanalen_django_api_client.api.videos import videos_retrieve
from loguru import logger

from .config import GRAPHICS_LAYER, VIDEO_LAYER
from .video import PrerecordedVideo
from .schedule_api import ScheduleFetcher

# Graphics URL for generating graphics between videos
GRAPHICS_URL = "https://frikanalen.no/graphics/"


async def load_schedule(api_url="https://frikanalen.no/"):
    """Load and parse schedule from the API with automatic graphics insertion.

    Args:
        api_url: Base URL for the Frikanalen API (default: "https://frikanalen.no/")

    Returns:
        list: List of schedule items (PrerecordedVideo and Graphic instances)
    """
    import asyncio

    from .items import Graphic  # Import here to avoid circular dependency

    # Fetch schedule items from the API
    client = Client(api_url)
    fetcher = ScheduleFetcher(client)

    async with client:
        schedule_items = await fetcher.get_schedule(date="today", days=1, surrounding=True)

        # Get unique video IDs
        video_ids = list({item.video.id for item in schedule_items})

        # Fetch full video details (including files) for all videos in parallel
        logger.info(f"Fetching video files for {len(video_ids)} videos")
        video_details_tasks = [get_video_files(vid, client) for vid in video_ids]
        video_files_results = await asyncio.gather(*video_details_tasks)

        # Create mapping of video_id -> files dict
        video_files_map = dict(zip(video_ids, video_files_results))

    schedule = []

    # Convert API items to PrerecordedVideo instances with pre-fetched files
    for item in schedule_items:
        video = item.video
        framerate = video.framerate  # Use actual framerate from API
        schedule.append(
            PrerecordedVideo(
                video.id,
                VIDEO_LAYER,
                framerate,
                item.starttime,
                item.endtime,
                video_files=video_files_map.get(video.id),
            )
        )

    # Generate and insert graphics between consecutive videos
    graphics = []
    for video_before, video_after in pairwise(schedule):
        duration_ms = int((video_after.start_time - video_before.end_time).total_seconds() * 1000)
        url = f"{GRAPHICS_URL}?duration={duration_ms}"
        graphics.append(Graphic(url, GRAPHICS_LAYER, video_before.end_time, video_after.start_time))

    # Combine videos and graphics, sorted by start time
    all_items = schedule + graphics
    all_items.sort(key=lambda x: x.start_time)

    logger.info(f"Loaded {len(schedule)} videos and generated {len(graphics)} graphics")
    return all_items


async def get_video_files(video_id: int, client: Client | None = None) -> dict[str, str]:
    """Fetch video files dict from a video's details.

    Args:
        video_id: The video ID to fetch files for
        client: Optional Client instance. If not provided, creates a new one.

    Returns:
        Dictionary mapping format names (e.g., 'broadcast', 'original') to file URLs/paths.
    """
    if client is None:
        client = Client("https://frikanalen.no/")
        async with client:
            return await _fetch_video_files(video_id, client)
    else:
        return await _fetch_video_files(video_id, client)


async def _fetch_video_files(video_id: int, client: Client) -> dict[str, str]:
    """Internal function to fetch video details and extract files dict."""
    response = await videos_retrieve.asyncio_detailed(
        id=str(video_id),
        client=client,  # type: ignore
    )

    if response.parsed is None:
        logger.error(f"Could not get video details from API, HTTP {response.status_code}")
        return {}

    video = response.parsed

    # The files field is a VideoFiles model with additional_properties dict
    files_dict = video.files.additional_properties

    logger.debug(
        f"Found {len(files_dict)} video files for video {video_id}: {list(files_dict.keys())}"
    )
    return files_dict
