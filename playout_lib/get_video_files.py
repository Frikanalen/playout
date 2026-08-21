from loguru import logger

from frikanalen_django_api_client import Client
from frikanalen_django_api_client.api.videofiles import videofiles_list
from frikanalen_django_api_client.api.videos import videos_retrieve
from frikanalen_django_api_client.models.paginated_video_file_list import PaginatedVideoFileList
from frikanalen_django_api_client.models.video import Video
from frikanalen_django_api_client.models.video_file import VideoFile

# A video has a handful of files at most; one page is always enough.
VIDEO_FILE_PAGE_SIZE = 50


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


async def get_video_file_records(
    video_id: int, client: Client | None = None
) -> dict[str, VideoFile]:
    """Fetch the video file records for a video, keyed by variant.

    The video detail endpoint only gives filenames; the loudness measurements
    live on the file records themselves, so they need a separate lookup.

    Args:
        video_id: The video ID to fetch file records for
        client: Optional Client instance. If not provided, creates a new one.

    Returns:
        Dictionary mapping variant name (e.g. 'broadcast') to its VideoFile,
        empty if the lookup fails.
    """
    if client is None:
        client = Client("https://frikanalen.no/")
        async with client:
            return await _fetch_video_file_records(video_id, client)
    else:
        return await _fetch_video_file_records(video_id, client)


async def _fetch_video_file_records(video_id: int, client: Client) -> dict[str, VideoFile]:
    """Internal function to fetch a video's file records."""
    response = await videofiles_list.asyncio_detailed(
        video_id=video_id,
        limit=VIDEO_FILE_PAGE_SIZE,
        client=client,  # type: ignore
    )

    if not isinstance(response.parsed, PaginatedVideoFileList):
        logger.error(
            f"Could not get file records for video {video_id}, HTTP {response.status_code}"
        )
        return {}

    return {file.variant.value: file for file in response.parsed.results}
