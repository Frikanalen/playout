"""API and data fetching functionality for schedule and video files."""

from datetime import datetime, time, timedelta
from itertools import pairwise
from urllib.parse import urlencode

import pytz
from loguru import logger

from frikanalen_django_api_client import Client
from playout_lib.get_video_files import get_video_details, get_video_file_records

from .config import GRAPHICS_LAYER, GRAPHICS_URL, NOTICE_LAYER, VIDEO_LAYER
from .items import FillerLoop, Graphic, ProgrammeUnavailable, localtime
from .live import LiveTransmission
from .schedule_api import ScheduleFetcher
from .video import PrerecordedVideo

# Gaps shorter than this just loop the filler reel instead of showing a
# proper graphics overlay.
MINIMUM_GRAPHIC_DURATION = timedelta(seconds=30)
# How far past the start of today a graphic covers when nothing is scheduled
# after it. The next load moves its end once something is booked.
LOOKAHEAD = timedelta(days=2)
OSLO = pytz.timezone("Europe/Oslo")


async def load_schedule(api_url="https://frikanalen.tv/"):
    """Load and parse schedule from the API with automatic graphics insertion.

    Args:
        api_url: Base URL for the Frikanalen API (default: "https://frikanalen.tv/")

    Returns:
        list: List of schedule items (PrerecordedVideo, LiveTransmission and Graphic instances)
    """
    import asyncio

    # Fetch schedule items from the API
    client = Client(api_url, raise_on_unexpected_status=True)
    fetcher = ScheduleFetcher(client)

    async with client:
        schedule_items = await fetcher.get_schedule(date="today", days=1, surrounding=True)

        # A live slot plays its source, not its video, so it needs no files
        video_ids = list(
            {item.video.id for item in schedule_items if item.video and not item.live_transmission}
        )

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
        if item.live_transmission:
            schedule.append(
                LiveTransmission(
                    item.live_transmission.stream_id, VIDEO_LAYER, item.starttime, item.endtime
                )
            )
            continue
        if not item.video:
            logger.error(f"Schedule item {item.id} has neither a video nor a live source")
            continue

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

        video = PrerecordedVideo(
            video_id,
            VIDEO_LAYER,
            framerate,
            item.starttime,
            item.endtime,
            video_details=video_details,
            video_files=video_files,
            video_file_records=file_records_map.get(video_id, {}),
        )
        if video.file_missing:
            logger.warning(f"Video {video_id} has no file yet, showing a notice in its slot")
            notice = unavailable_notice(schedule, item.video.name, video_id, item)
            if notice is not None:
                schedule.append(notice)
        else:
            schedule.append(video)

    schedule.sort(key=lambda x: x.start_time)
    graphics = fill_gaps(schedule, start_of_day(localtime()))

    all_items = schedule + graphics
    all_items.sort(key=lambda x: x.start_time)

    logger.info(f"Loaded {len(schedule)} programmes and generated {len(graphics)} graphics")
    return all_items


def start_of_day(now: datetime) -> datetime:
    """Midnight in Oslo on the day of now."""
    return OSLO.localize(datetime.combine(now.astimezone(OSLO).date(), time.min))


def unavailable_notice(schedule, title, video_id, item):
    """A notice for a programme with no file, or None if it extends the one before.

    Two missing programmes back to back share one notice: they would share
    its layer too, and one graphic clears the layer as the next one starts.
    """
    previous = schedule[-1] if schedule else None
    if isinstance(previous, ProgrammeUnavailable) and previous.end_time == item.starttime:
        previous.title = ""
        previous.reschedule(item.endtime)
        previous.url = notice_url(previous.start_time, previous.end_time, "")
        return None
    return ProgrammeUnavailable(
        notice_url(item.starttime, item.endtime, title),
        NOTICE_LAYER,
        item.starttime,
        item.endtime,
        video_id,
        title,
    )


def notice_url(start, end, title):
    duration_ms = int((end - start).total_seconds() * 1000)
    return f"{GRAPHICS_URL}?{urlencode({'duration': duration_ms, 'unavailable': title})}"


def fill_gaps(programmes, day_start):
    """Graphics for all the time nothing is scheduled.

    The jukebox no longer fills the schedule, so this covers every gap: the
    holes between programmes, the time before the first and after the last,
    and a day with nothing on at all. Gaps too short for a graphic loop the
    filler reel instead.
    """
    horizon = day_start + LOOKAHEAD
    if not programmes:
        return [gap_item(day_start, horizon)]

    gaps = list(pairwise(programmes))
    fill = [gap_item(before.end_time, after.start_time) for before, after in gaps]
    if programmes[0].start_time > day_start:
        fill.insert(0, gap_item(day_start, programmes[0].start_time))
    if programmes[-1].end_time < horizon:
        fill.append(gap_item(programmes[-1].end_time, horizon))
    return [item for item in fill if item is not None]


def gap_item(start, end):
    """A graphic for the gap from start to end, or a filler loop if it is short."""
    gap = end - start
    if gap <= timedelta(0):
        return None
    if gap < MINIMUM_GRAPHIC_DURATION:
        return FillerLoop(GRAPHICS_LAYER, start, end)
    duration_ms = int(gap.total_seconds() * 1000)
    return Graphic(f"{GRAPHICS_URL}?duration={duration_ms}", GRAPHICS_LAYER, start, end)
