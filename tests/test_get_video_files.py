from http import HTTPStatus

from frikanalen_django_api_client.models import PaginatedVideoFileList
from playout_lib import get_video_files

from .factories import make_response, make_video, make_video_file


class TestGetVideoDetails:
    async def test_returns_video_when_found(self, monkeypatch):
        video = make_video(42, broadcast="broadcast.mp4")

        async def fake_call(*, id, client):
            assert id == "42"
            return make_response(video)

        monkeypatch.setattr(get_video_files.videos_retrieve, "asyncio_detailed", fake_call)

        result = await get_video_files.get_video_details(42, client="fake-client")

        assert result is video

    async def test_returns_none_when_not_found(self, monkeypatch):
        async def fake_call(*, id, client):
            return make_response(None, status_code=HTTPStatus.NOT_FOUND)

        monkeypatch.setattr(get_video_files.videos_retrieve, "asyncio_detailed", fake_call)

        result = await get_video_files.get_video_details(42, client="fake-client")

        assert result is None

    async def test_creates_own_client_when_none_given(self, monkeypatch):
        created_clients = []

        class FakeClient:
            async def __aenter__(self):
                created_clients.append(self)
                return self

            async def __aexit__(self, *args):
                return None

        monkeypatch.setattr(get_video_files, "Client", lambda base_url: FakeClient())

        async def fake_fetch(video_id, client):
            assert client in created_clients
            return make_video(video_id)

        monkeypatch.setattr(get_video_files, "_fetch_video_details", fake_fetch)

        result = await get_video_files.get_video_details(7)

        assert result.id == 7
        assert len(created_clients) == 1


class TestGetVideoFileRecords:
    async def test_returns_records_keyed_by_variant(self, monkeypatch):
        files = [
            make_video_file(variant="broadcast", integrated_lufs=-23.5),
            make_video_file(variant="original", integrated_lufs=-19.0),
        ]

        async def fake_call(*, video_id, limit, client):
            assert video_id == 42
            return make_response(PaginatedVideoFileList(count=len(files), results=files))

        monkeypatch.setattr(get_video_files.videofiles_list, "asyncio_detailed", fake_call)

        result = await get_video_files.get_video_file_records(42, client="fake-client")

        assert set(result) == {"broadcast", "original"}
        assert result["broadcast"].integrated_lufs == -23.5

    async def test_returns_empty_dict_when_the_lookup_fails(self, monkeypatch):
        async def fake_call(*, video_id, limit, client):
            return make_response(None, status_code=HTTPStatus.NOT_FOUND)

        monkeypatch.setattr(get_video_files.videofiles_list, "asyncio_detailed", fake_call)

        result = await get_video_files.get_video_file_records(42, client="fake-client")

        assert result == {}
