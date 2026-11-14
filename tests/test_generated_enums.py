"""The generated client's enums accept values newer than playout's schema.

See client-templates/README.md for why.
"""

import pytest

from frikanalen_django_api_client.models import (
    SchedulereasonEnum,
    VideoFile,
    VideoFileVariantEnum,
)


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
