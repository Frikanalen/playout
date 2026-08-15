"""Builders for frikanalen_django_api_client model objects used across tests."""

from http import HTTPStatus

from frikanalen_django_api_client.models import (
    ScheduleitemOrganization,
    ScheduleitemRead,
    ScheduleitemVideo,
    Video,
    VideoFiles,
)
from frikanalen_django_api_client.types import Response


def make_org(id_=1, name="Test Org"):
    return ScheduleitemOrganization(id=id_, name=name, description="")


def make_scheduleitem_video(video_id, name="Test Video"):
    return ScheduleitemVideo(id=video_id, name=name, organization=make_org(), categories=[])


def make_scheduleitem(item_id, video_id, start_time, end_time):
    return ScheduleitemRead(
        id=item_id,
        video=make_scheduleitem_video(video_id),
        starttime=start_time,
        endtime=end_time,
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
        organization=make_org(),
        categories=[],
        framerate=framerate,
        created_time=None,
        updated_time=None,
        ogv_url="",
        large_thumbnail_url="",
    )


def make_response(parsed, status_code=HTTPStatus.OK):
    return Response(status_code=status_code, content=b"", headers={}, parsed=parsed)
