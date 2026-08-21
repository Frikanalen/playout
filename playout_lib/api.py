"""API and data fetching functionality for schedule and video files."""

from datetime import timedelta
from itertools import pairwise

from loguru import logger

from frikanalen_django_api_client import Client
from playout_lib.get_video_files import get_video_details, get_video_file_records

from .config import GRAPHICS_LAYER, GRAPHICS_URL, VIDEO_LAYER
from .schedule_api import ScheduleFetcher
from .video import PrerecordedVideo

# Gaps shorter than this just loop the filler reel instead of showing a
# proper graphics overlay.
MINIMUM_GRAPHIC_DURATION = timedelta(seconds=30)


async def load_schedule(api_url="https://frikanalen.no/"):
    """Load and parse schedule from the API with automatic graphics insertion.

    Args:
        api_url: Base URL for the Frikanalen API (default: "https://frikanalen.no/")

    Returns:
        list: List of schedule items (PrerecordedVideo and Graphic instances)
    """
    import asyncio

    from .items import FillerLoop, Graphic  # Import here to avoid circular dependency

    # Fetch schedule items from the API
    client = Client(api_url, raise_on_unexpected_status=True)
    fetcher = ScheduleFetcher(client)

    async with client:
        schedule_items = await fetcher.get_schedule(date="today", days=1, surrounding=True)

        # Get unique video IDs
        video_ids = list({item.video.id for item in schedule_items})

        # Fetch full video details (including files and framerate) for all videos in
        # parallel, along with the file records that carry the loudness measurements
        logger.info(f"Fetching video details for {len(video_ids)} videos")
        video_details_task = asyncio.gather(*[get_video_details(vid, client) for vid in video_ids])
        file_records_task = asyncio.gather(
            *[get_video_file_records(vid, client) for vid in video_ids],
            # Loudness is a nicety; never let a failed lookup take the channel
            # off air. A video with no records just plays at its recorded level.
            return_exceptions=True,
        )
        video_details_results, file_records_results = await asyncio.gather(
            video_details_task, file_records_task
        )

        # Create mapping of video_id -> Video object
        video_details_map = dict(zip(video_ids, video_details_results, strict=True))

        file_records_map = {}
        for vid, result in zip(video_ids, file_records_results, strict=True):
            if isinstance(result, BaseException):
                logger.warning(
                    f"Could not fetch file records for video {vid} "
                    f"({result}), playing it unnormalized"
                )
                file_records_map[vid] = {}
            else:
                file_records_map[vid] = result

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
                video_file_records=file_records_map.get(video_id, {}),
            )
        )

    # Generate and insert graphics (or, for short gaps, a plain filler loop)
    # between consecutive videos
    graphics = []
    for video_before, video_after in pairwise(schedule):
        gap = video_after.start_time - video_before.end_time
        if gap >= MINIMUM_GRAPHIC_DURATION:
            duration_ms = int(gap.total_seconds() * 1000)
            url = f"{GRAPHICS_URL}?duration={duration_ms}"
            graphics.append(
                Graphic(url, GRAPHICS_LAYER, video_before.end_time, video_after.start_time)
            )
        else:
            graphics.append(
                FillerLoop(GRAPHICS_LAYER, video_before.end_time, video_after.start_time)
            )

    # Combine videos and graphics, sorted by start time
    all_items = schedule + graphics
    all_items.sort(key=lambda x: x.start_time)

    logger.info(f"Loaded {len(schedule)} videos and generated {len(graphics)} graphics")
    return all_items
