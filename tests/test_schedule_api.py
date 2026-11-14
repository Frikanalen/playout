import datetime

import httpx
import pytest

from frikanalen_django_api_client import Client
from frikanalen_django_api_client.models import ScheduleitemRead
from playout_lib.schedule_api import ScheduleFetcher


def item_json(item_id, video_id=1, start="2026-01-01T10:00:00+01:00"):
    """A schedule item as the API sends it."""
    return {
        "id": item_id,
        "defaultName": "Test Video",
        "video": {
            "id": video_id,
            "name": "Test Video",
            "organization": {"id": 1, "name": "Test Org", "description": ""},
            "categories": [],
            "files": [],
        },
        "schedulereason": 3,
        "starttime": start,
        "endtime": "2026-01-01T12:00:00+01:00",
        "duration": "00:30:00",
        "grant": None,
        "isLive": False,
        "liveSource": None,
    }


def page(results, next_=None):
    return {"count": len(results), "next": next_, "previous": None, "results": results}


def fetcher(handler):
    """A ScheduleFetcher whose HTTP requests are answered by handler."""
    client = Client("http://api.test/", httpx_args={"transport": httpx.MockTransport(handler)})
    return ScheduleFetcher(client)


def answering(*pages, requests=None):
    """A handler returning pages in turn; an int is answered as that HTTP status."""
    remaining = list(pages)

    def handler(request):
        if requests is not None:
            requests.append(request)
        answer = remaining.pop(0)
        if isinstance(answer, int):
            return httpx.Response(answer)
        if isinstance(answer, bytes):
            return httpx.Response(200, content=answer)
        return httpx.Response(200, json=answer)

    return handler


class TestGetSchedule:
    async def test_single_page_returns_all_items(self):
        result = await fetcher(answering(page([item_json(1)]))).get_schedule()

        assert [item.id for item in result] == [1]
        assert isinstance(result[0], ScheduleitemRead)

    async def test_follows_pagination_until_next_is_none(self):
        requests = []
        handler = answering(
            page([item_json(1)], next_="http://api.test/?offset=100"),
            page([item_json(2)]),
            requests=requests,
        )

        result = await fetcher(handler).get_schedule()

        assert [item.id for item in result] == [1, 2]
        assert [r.url.params["offset"] for r in requests] == ["0", "100"]

    async def test_returns_partial_results_when_a_later_page_fails(self):
        handler = answering(page([item_json(1)], next_="http://api.test/?offset=100"), 500)

        result = await fetcher(handler).get_schedule()

        assert [item.id for item in result] == [1]

    async def test_raises_when_first_page_fails(self):
        with pytest.raises(RuntimeError):
            await fetcher(answering(500)).get_schedule()

    async def test_raises_when_the_first_page_is_not_a_schedule(self):
        with pytest.raises(RuntimeError):
            await fetcher(answering(b"<html>gateway error</html>")).get_schedule()

    async def test_raises_when_the_api_is_unreachable(self):
        def handler(request):
            raise httpx.ConnectError("refused")

        with pytest.raises(RuntimeError):
            await fetcher(handler).get_schedule()

    async def test_an_empty_schedule_is_an_empty_list(self):
        # Unprogrammed time airs graphics, so nothing scheduled is no error.
        assert await fetcher(answering(page([]))).get_schedule() == []

    async def test_skips_an_item_it_cannot_read_and_keeps_the_rest(self):
        # 2026-11-14: a file variant newer than playout's pinned schema made
        # the generated parser reject the whole page, so nothing new aired
        # for six hours. One unreadable item must cost only its own slot.
        bad_video = item_json(2, start="2026-01-01T11:00:00+01:00")
        del bad_video["video"]["organization"]
        bad_shape = item_json(3)
        del bad_shape["starttime"]

        result = await fetcher(
            answering(page([item_json(1), bad_video, bad_shape, item_json(4)]))
        ).get_schedule()

        assert [item.id for item in result] == [1, 4]

    async def test_keeps_an_item_listing_a_file_variant_it_does_not_know(self):
        # Exactly what happened on 2026-11-14 with "hls": the files listed on
        # a schedule item are informational, so the programme still airs.
        item = item_json(1)
        item["video"]["files"] = [
            {"id": 1, "variant": "broadcast", "filename": "a.mxf"},
            {"id": 2, "variant": "from-the-future", "filename": "b.m3u8"},
        ]

        result = await fetcher(answering(page([item]))).get_schedule()

        assert [item.id for item in result] == [1]
        assert [f.filename for f in result[0].video.files] == ["a.mxf"]

    async def test_passes_date_days_and_surrounding_through(self):
        requests = []
        handler = answering(page([item_json(1)]), requests=requests)

        await fetcher(handler).get_schedule(date="2026-01-01", days=2, surrounding=True)

        params = requests[0].url.params
        assert params["date"] == "2026-01-01"
        assert params["days"] == "2"
        assert params["surrounding"] == "true"

    async def test_omits_date_when_asking_for_today(self):
        # The schema types `date` as a date, so the 'today' the API documents
        # cannot be sent as a string. Leaving it unset selects today instead.
        requests = []

        await fetcher(answering(page([item_json(1)]), requests=requests)).get_schedule(date="today")

        assert "date" not in requests[0].url.params

    async def test_omits_date_when_none_given(self):
        requests = []

        await fetcher(answering(page([item_json(1)]), requests=requests)).get_schedule()

        assert "date" not in requests[0].url.params


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
