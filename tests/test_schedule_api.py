import datetime
from http import HTTPStatus

import pytest

from frikanalen_django_api_client.models import PaginatedScheduleitemReadList
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

    async def test_raises_when_results_are_empty(self, monkeypatch):
        async def fake_call(**kwargs):
            return make_response(page([]))

        monkeypatch.setattr(schedule_api.scheduleitems_list, "asyncio_detailed", fake_call)

        with pytest.raises(RuntimeError):
            await ScheduleFetcher(client=None).get_schedule()

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
