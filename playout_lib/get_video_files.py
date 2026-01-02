from frikanalen_django_api_client import Client
from frikanalen_django_api_client.api.videos import videos_retrieve
from frikanalen_django_api_client.models.video import Video
from loguru import logger


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


# Backward compatibility wrapper
async def get_video_files(video_id: int, client: Client | None = None) -> dict[str, str]:
    """Fetch video files dict from a video's details.

    DEPRECATED: Use get_video_details() instead to preserve all video metadata.

    Args:
        video_id: The video ID to fetch files for
        client: Optional Client instance. If not provided, creates a new one.

    Returns:
        Dictionary mapping format names (e.g., 'broadcast', 'original') to file URLs/paths.
    """
    video = await get_video_details(video_id, client)
    if video is None:
        return {}
    return video.files.additional_properties
