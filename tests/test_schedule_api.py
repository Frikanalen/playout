import datetime
from http import HTTPStatus

import pytest

from frikanalen_django_api_client.models import PaginatedScheduleitemReadList, ScheduleitemRead
from frikanalen_django_api_client.types import UNSET
from playout_lib import schedule_api
from playout_lib.schedule_api import ScheduleFetcher

from .factories import make_response, make_scheduleitem


def page(results, next_=None):
    return PaginatedScheduleitemReadList(count=len(results), results=results, next_=next_)


class TestGetSchedule:
    async def test_single_page_returns_all_items(self, monkeypatch):
        items = [make_scheduleitem(1, 1, "2026-01-01T10:00:00+01:00", "2026-01-01T10:30:00+01:00")]

        async def fake_call(**kwargs):
            return make_response(page(items))

        monkeypatch.setattr(schedule_api.scheduleitems_list, "asyncio_detailed", fake_call)

        result = await ScheduleFetcher(client=None).get_schedule()

        assert result == items

    async def test_follows_pagination_until_next_is_none(self, monkeypatch):
        first_page_items = [
            make_scheduleitem(1, 1, "2026-01-01T10:00:00+01:00", "2026-01-01T10:30:00+01:00")
        ]
        second_page_items = [
            make_scheduleitem(2, 2, "2026-01-01T11:00:00+01:00", "2026-01-01T11:30:00+01:00")
        ]
        calls = []

        async def fake_call(**kwargs):
            calls.append(kwargs["offset"])
            if kwargs["offset"] == 0:
                return make_response(page(first_page_items, next_="http://example.com/?offset=100"))
            return make_response(page(second_page_items, next_=None))

        monkeypatch.setattr(schedule_api.scheduleitems_list, "asyncio_detailed", fake_call)

        result = await ScheduleFetcher(client=None).get_schedule()

        assert result == first_page_items + second_page_items
        assert calls == [0, 100]

    async def test_returns_partial_results_when_a_later_page_fails(self, monkeypatch):
        first_page_items = [
            make_scheduleitem(1, 1, "2026-01-01T10:00:00+01:00", "2026-01-01T10:30:00+01:00")
        ]
        calls = {"n": 0}

        async def fake_call(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return make_response(page(first_page_items, next_="http://example.com/?offset=100"))
            return make_response(None, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        monkeypatch.setattr(schedule_api.scheduleitems_list, "asyncio_detailed", fake_call)

        result = await ScheduleFetcher(client=None).get_schedule()

        assert result == first_page_items

    async def test_raises_when_first_page_fails(self, monkeypatch):
        async def fake_call(**kwargs):
            return make_response(None, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        monkeypatch.setattr(schedule_api.scheduleitems_list, "asyncio_detailed", fake_call)

        with pytest.raises(RuntimeError):
            await ScheduleFetcher(client=None).get_schedule()

    async def test_raises_when_parsed_is_none(self, monkeypatch):
        async def fake_call(**kwargs):
            return make_response(None, status_code=HTTPStatus.OK)

        monkeypatch.setattr(schedule_api.scheduleitems_list, "asyncio_detailed", fake_call)

        with pytest.raises(RuntimeError):
            await ScheduleFetcher(client=None).get_schedule()

    async def test_an_empty_schedule_is_an_empty_list(self, monkeypatch):
        # Unprogrammed time airs graphics, so nothing scheduled is no error.
        async def fake_call(**kwargs):
            return make_response(page([]))

        monkeypatch.setattr(schedule_api.scheduleitems_list, "asyncio_detailed", fake_call)

        assert await ScheduleFetcher(client=None).get_schedule() == []

    async def test_passes_date_days_and_surrounding_through(self, monkeypatch):
        captured = {}

        item = make_scheduleitem(1, 1, "2026-01-01T10:00:00+01:00", "2026-01-01T10:30:00+01:00")

        async def fake_call(**kwargs):
            captured.update(kwargs)
            return make_response(page([item]))

        monkeypatch.setattr(schedule_api.scheduleitems_list, "asyncio_detailed", fake_call)

        await ScheduleFetcher(client=None).get_schedule(date="2026-01-01", days=2, surrounding=True)

        assert captured["date"] == datetime.date(2026, 1, 1)
        assert captured["days"] == 2
        assert captured["surrounding"] is True
        assert captured["include_posters"] is True

    async def test_omits_date_when_asking_for_today(self, monkeypatch):
        # The schema types `date` as a date, so the 'today' the API documents
        # cannot be sent as a string. Leaving it unset selects today instead.
        captured = {}

        item = make_scheduleitem(1, 1, "2026-01-01T10:00:00+01:00", "2026-01-01T10:30:00+01:00")

        async def fake_call(**kwargs):
            captured.update(kwargs)
            return make_response(page([item]))

        monkeypatch.setattr(schedule_api.scheduleitems_list, "asyncio_detailed", fake_call)

        await ScheduleFetcher(client=None).get_schedule(date="today")

        assert captured["date"] is UNSET

    async def test_omits_date_when_none_given(self, monkeypatch):
        captured = {}

        item = make_scheduleitem(1, 1, "2026-01-01T10:00:00+01:00", "2026-01-01T10:30:00+01:00")

        async def fake_call(**kwargs):
            captured.update(kwargs)
            return make_response(page([item]))

        monkeypatch.setattr(schedule_api.scheduleitems_list, "asyncio_detailed", fake_call)

        await ScheduleFetcher(client=None).get_schedule()

        assert captured["date"] is UNSET


class TestScheduleitemShape:
    """The schedule item as the API sends it since live moved onto videos."""

    ITEM = {
        "id": 1,
        "defaultName": "",
        "video": None,
        "schedulereason": None,
        "starttime": "2026-01-01T10:00:00+01:00",
        "endtime": "2026-01-01T10:30:00+01:00",
        "duration": "00:30:00",
        "grant": 7,
        "isLive": False,
        "liveSource": None,
    }

    def test_parses_a_compiled_item(self):
        item = ScheduleitemRead.from_dict(self.ITEM)

        assert item.endtime == datetime.datetime.fromisoformat("2026-01-01T10:30:00+01:00")
        assert item.live_source is None

    def test_parses_a_live_airing_with_its_source(self):
        stream_id = "1b4e28ba-2fa1-11d2-883f-0016d3cca427"
        item = ScheduleitemRead.from_dict(
            dict(self.ITEM, isLive=True, liveSource={"id": 3, "streamId": stream_id})
        )

        assert item.is_live
        assert str(item.live_source.stream_id) == stream_id

    def test_an_api_from_before_posters_has_none(self):
        # ITEM has no "poster" key at all, as an older API sends it.
        assert not ScheduleitemRead.from_dict(self.ITEM).poster

    def test_parses_a_poster_and_a_template_it_does_not_know(self):
        poster = {
            "id": 4,
            "template": "a-template-added-later",
            "heading": "Neste: debatt",
            "text": "",
            "organization": {"id": 1, "name": "Org", "description": ""},
            "updatedAt": "2026-01-01T09:00:00+01:00",
        }
        item = ScheduleitemRead.from_dict(dict(self.ITEM, poster=poster))

        assert item.poster.heading == "Neste: debatt"
        assert item.poster.template == "a-template-added-later"
