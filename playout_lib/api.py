"""API and data fetching functionality for schedule and video files."""

from itertools import pairwise

from frikanalen_django_api_client import Client
from loguru import logger

from playout_lib.get_video_files import get_video_details

from .config import GRAPHICS_LAYER, VIDEO_LAYER
from .schedule_api import ScheduleFetcher
from .video import PrerecordedVideo

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
    client = Client(api_url, raise_on_unexpected_status=True)
    fetcher = ScheduleFetcher(client)

    async with client:
        schedule_items = await fetcher.get_schedule(date="today", days=1, surrounding=True)

        # Get unique video IDs
        video_ids = list({item.video.id for item in schedule_items})

        # Fetch full video details (including files and framerate) for all videos in parallel
        logger.info(f"Fetching video details for {len(video_ids)} videos")
        video_details_tasks = [get_video_details(vid, client) for vid in video_ids]
        video_details_results = await asyncio.gather(*video_details_tasks)

        # Create mapping of video_id -> Video object
        video_details_map = dict(zip(video_ids, video_details_results, strict=True))

    schedule = []

    # Convert API items to PrerecordedVideo instances with pre-fetched details
    for item in schedule_items:
        video_id = item.video.id
        video_details = video_details_map.get(video_id)

        # Use framerate from detailed video object if available
        # Detailed video object should always be available since we just fetched it
        if video_details:
            framerate = video_details.framerate
            video_files = video_details.files.additional_properties
        else:
            # Fallback: this shouldn't happen but handle gracefully
            framerate = 25000  # Default to 25fps if we can't determine
            video_files = None
            logger.warning(f"No detailed video info for video {video_id}, using default framerate")

        schedule.append(
            PrerecordedVideo(
                video_id,
                VIDEO_LAYER,
                framerate,
                item.starttime,
                item.endtime,
                video_details=video_details,
                video_files=video_files,
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
