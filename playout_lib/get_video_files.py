from loguru import logger

from frikanalen_django_api_client import Client
from frikanalen_django_api_client.api.videos import videos_retrieve
from frikanalen_django_api_client.models.video import Video


async def get_video_details(video_id: int, client: Client | None = None) -> Video | None:
    """Fetch complete video details from the API.

    Args:
        video_id: The video ID to fetch details for
        client: Optional Client instance. If not provided, creates a new one.

    Returns:
        Complete Video object with all details including framerate and files,
        or None if fetch fails.
    """
    if client is None:
        client = Client("https://frikanalen.no/")
        async with client:
            return await _fetch_video_details(video_id, client)
    else:
        return await _fetch_video_details(video_id, client)


async def _fetch_video_details(video_id: int, client: Client) -> Video | None:
    """Internal function to fetch complete video details."""
    response = await videos_retrieve.asyncio_detailed(
        id=str(video_id),
        client=client,  # type: ignore
    )

    if response.parsed is None:
        logger.error(f"Could not get video details from API, HTTP {response.status_code}")
        return None

    video = response.parsed

    files_dict = video.files.additional_properties
    logger.debug(
        f"Found {len(files_dict)} video files for video {video_id}: {list(files_dict.keys())}"
    )
    return video
