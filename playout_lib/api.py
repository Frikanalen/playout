"""API and data fetching functionality for schedule and video files."""

import aiohttp
import requests
from dateutil.parser import parse
from loguru import logger

from .config import API_URL, GRAPHICS_LAYER, LEGACY_URL, VIDEO_LAYER


async def fetch(url):
    """Fetch JSON data from a URL asynchronously."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()


async def load_schedule(api_url=API_URL):
    """Load and parse schedule from the API.

    Returns:
        list: List of schedule items (PrerecordedVideo or Graphic instances)
    """
    from .items import Graphic, PrerecordedVideo  # Import here to avoid circular dependency

    schedule_json = await fetch(api_url)
    schedule = []

    for item in schedule_json["items"]:
        start_time = parse(item["startTime"])
        end_time = parse(item["endTime"])
        logger.warning(f"{start_time} og {end_time}")

        if item["type"] == "video":
            schedule.append(
                PrerecordedVideo(
                    item["videoID"], VIDEO_LAYER, item["framerate"], start_time, end_time
                )
            )
        elif item["type"] == "graphics":
            schedule.append(Graphic(item["url"], GRAPHICS_LAYER, start_time, end_time))

    return schedule


class VideoFiles:
    """Manager for retrieving video file paths from the API."""

    def __init__(self, video_id):
        self.video_id = video_id

    def __getitem__(self, file_type):
        """Get video file path by type (e.g., 'broadcast' or 'original').

        Args:
            file_type (str): The file type/format name

        Returns:
            str: Filename path or None if not found

        Raises:
            Exception: If API request fails
        """
        params = {"video_id": self.video_id, "format__fsname": file_type}
        res = requests.get(LEGACY_URL + "videofiles/", params=params)

        if res.status_code != requests.codes.ok:
            raise Exception(f"Could not get video files from API, HTTP {res.status_code}")

        try:
            data = res.json()
        except Exception:
            raise

        if data["count"] == 0:
            return None

        if data["count"] > 1:
            logger.warning(
                f"<1 video files returned for video {self.video_id} type {file_type}, returning 1"
            )

        return data["results"][0]["filename"]
