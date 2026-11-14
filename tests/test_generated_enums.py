"""The generated client's enums accept values newer than playout's schema.

See client-templates/README.md for why.
"""

import httpx
import pytest

from frikanalen_django_api_client import Client
from frikanalen_django_api_client.models import (
    SchedulereasonEnum,
    VideoFile,
    VideoFileVariantEnum,
)
from playout_lib import get_video_files

NEW_VARIANT = "av1_hdr"  # anything the pinned schema has never heard of


def test_known_values_are_the_usual_members():
    assert VideoFileVariantEnum("broadcast") is VideoFileVariantEnum.BROADCAST
    assert SchedulereasonEnum(3) is SchedulereasonEnum.VALUE_3


def test_a_new_string_value_is_an_unknown_member():
    variant = VideoFileVariantEnum("from-the-future")

    assert isinstance(variant, VideoFileVariantEnum)
    assert variant.name == "UNKNOWN"
    assert variant.value == "from-the-future"
    assert str(variant) == "from-the-future"
    assert variant not in list(VideoFileVariantEnum)
    assert variant != VideoFileVariantEnum.BROADCAST


def test_a_new_integer_value_is_an_unknown_member():
    reason = SchedulereasonEnum(99)

    assert reason.name == "UNKNOWN"
    assert reason.value == 99


def test_a_value_of_the_wrong_type_still_fails():
    with pytest.raises(ValueError):
        VideoFileVariantEnum(5)
    with pytest.raises(ValueError):
        SchedulereasonEnum("3")


def test_a_model_with_a_new_value_parses_and_round_trips():
    raw = {
        "id": 1,
        "createdTime": "2026-01-01T00:00:00Z",
        "video": 1,
        "variant": "from-the-future",
        "filename": "a.m3u8",
    }

    record = VideoFile.from_dict(raw)

    assert record.variant.value == "from-the-future"
    assert record.to_dict()["variant"] == "from-the-future"


def test_a_new_value_is_reported_once(caplog):
    with caplog.at_level("WARNING"):
        VideoFileVariantEnum("reported-once")
        VideoFileVariantEnum("reported-once")

    reports = [r for r in caplog.records if "reported-once" in r.getMessage()]
    assert len(reports) == 1
    assert "pinned schema doesn't list" in reports[0].getMessage()


def video_file(variant, file_id=1, lufs=None):
    return {
        "id": file_id,
        "createdTime": "2026-11-14T12:00:00Z",
        "video": 42,
        "variant": variant,
        "filename": f"42/{variant}/clip",
        "integratedLufs": lufs,
        "truepeakLufs": None,
        "profileRevision": 0,
    }


class TestFileRecordsWithAnUnknownVariant:
    async def test_the_known_records_still_come_through(self):
        """Through the real generated parser, as the API would send it.

        Before, the unknown variant failed the whole page, the video looked
        like it had no file, and an "unavailable" notice aired instead of it.
        """
        page = {
            "count": 2,
            "next": None,
            "previous": None,
            "results": [video_file("original", 1, -21.0), video_file(NEW_VARIANT, 2)],
        }

        def handler(request):
            assert request.url.path == "/api/videofiles"
            return httpx.Response(200, json=page)

        client = Client(
            base_url="https://api.test/", httpx_args={"transport": httpx.MockTransport(handler)}
        )
        async with client:
            records = await get_video_files.get_video_file_records(42, client)

        assert set(records) == {"original", NEW_VARIANT}
        assert records["original"].integrated_lufs == -21.0
