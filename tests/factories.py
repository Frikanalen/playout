"""Builders for frikanalen_django_api_client model objects used across tests."""

from datetime import UTC, datetime
from http import HTTPStatus

from frikanalen_django_api_client.models import (
    ScheduleitemOrganization,
    ScheduleitemRead,
    ScheduleitemVideo,
    Video,
    VideoFile,
    VideoFiles,
    VideoFileVariantEnum,
)
from frikanalen_django_api_client.types import UNSET, Response


def make_org(id_=1, name="Test Org"):
    return ScheduleitemOrganization(id=id_, name=name, description="")


def make_scheduleitem_video(video_id, name="Test Video", files=None):
    return ScheduleitemVideo(
        id=video_id,
        name=name,
        organization=make_org(),
        categories=[],
        files=files if files is not None else [],
    )


def make_scheduleitem(item_id, video_id, start_time, end_time, displaceable=False):
    return ScheduleitemRead(
        id=item_id,
        video=make_scheduleitem_video(video_id),
        starttime=start_time,
        endtime=end_time,
        displaceable=displaceable,
    )


def make_video_files(**files):
    vf = VideoFiles()
    vf.additional_properties = files
    return vf


def make_video(video_id, framerate=25000, name="Test Video", **files):
    return Video(
        id=video_id,
        name=name,
        files=make_video_files(**files),
        creator="test@example.com",
        organization=make_org(),
        duration_sec=None,
        categories=[],
        framerate=framerate,
        created_time=None,
        updated_time=None,
        ogv_url="",
        large_thumbnail_url="",
    )


def make_response(parsed, status_code=HTTPStatus.OK):
    return Response(status_code=status_code, content=b"", headers={}, parsed=parsed)


def make_video_file(
    file_id=1,
    video_id=1,
    variant="broadcast",
    filename="broadcast.mp4",
    integrated_lufs=UNSET,
    truepeak_lufs=UNSET,
):
    return VideoFile(
        id=file_id,
        created_time=datetime(2026, 1, 1, tzinfo=UTC),
        video=video_id,
        variant=VideoFileVariantEnum(variant),
        filename=filename,
        integrated_lufs=integrated_lufs,
        truepeak_lufs=truepeak_lufs,
    )


def make_video_file_records(**by_variant):
    """Build a variant -> VideoFile mapping from {variant: (lufs, truepeak)}."""
    return {
        variant: make_video_file(
            variant=variant,
            filename=f"{variant}.mp4",
            integrated_lufs=integrated_lufs,
            truepeak_lufs=truepeak_lufs,
        )
        for variant, (integrated_lufs, truepeak_lufs) in by_variant.items()
    }
