"""The generated client keeps enum values newer than the pinned schema.

On 2026-11-14 the API started listing HLS files before playout's schema knew
the variant, and one unreadable value failed whole responses: nothing new
aired for hours. client-templates/ makes the generated enums keep such values
instead, so only code that asks for a specific member notices them.
"""

import httpx

from frikanalen_django_api_client import Client
from frikanalen_django_api_client.models import (
    ScheduleitemRead,
    ScheduleitemVideo,
    VideoFile,
    VideoFileVariantEnum,
)
from playout_lib import get_video_files

NEW_VARIANT = "av1_hdr"  # anything the pinned schema has never heard of


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


class TestUnknownEnumValues:
    def test_an_unknown_value_is_kept_not_fatal(self):
        variant = VideoFileVariantEnum(NEW_VARIANT)

        assert variant.value == NEW_VARIANT
        assert variant == NEW_VARIANT
        assert str(variant) == NEW_VARIANT

    def test_known_values_are_still_the_real_members(self):
        assert VideoFileVariantEnum("broadcast") is VideoFileVariantEnum.BROADCAST
        assert NEW_VARIANT not in {member.value for member in VideoFileVariantEnum}

    def test_non_strings_are_still_refused(self):
        try:
            VideoFileVariantEnum(3)
        except ValueError:
            pass
        else:
            raise AssertionError("3 is not a file variant")

    def test_a_video_file_of_an_unknown_variant_parses(self):
        file = VideoFile.from_dict(video_file(NEW_VARIANT))

        assert file.variant.value == NEW_VARIANT

    def test_a_schedule_item_listing_an_unknown_variant_keeps_its_video(self):
        item = ScheduleitemRead.from_dict(
            {
                "id": 1,
                "defaultName": "",
                "video": {
                    "id": 42,
                    "name": "Programme",
                    "organization": {"id": 7, "name": "Org", "description": ""},
                    "categories": [],
                    "files": [
                        {"id": 1, "variant": "original", "filename": "42/original/clip.mp4"},
                        {"id": 2, "variant": NEW_VARIANT, "filename": "42/new/clip"},
                    ],
                },
                "schedulereason": None,
                "starttime": "2026-01-01T10:00:00+01:00",
                "endtime": "2026-01-01T10:30:00+01:00",
                "duration": "00:30:00",
                "grant": 7,
                "isLive": False,
                "liveSource": None,
            }
        )

        assert isinstance(item.video, ScheduleitemVideo)
        assert [f.variant.value for f in item.video.files] == ["original", NEW_VARIANT]


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
