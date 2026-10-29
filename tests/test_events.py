import asyncio

import httpx

from playout_lib import events

STREAM = (
    'retry: 2000\nevent: hello\ndata: {"type": "hello"}\n\n'
    ": keepalive\n\n"
    'event: schedule.changed\ndata: {"type": "schedule.changed"}\n\n'
)


async def test_every_event_asks_for_a_reload_and_a_drop_reconnects(monkeypatch):
    monkeypatch.setattr(events, "RECONNECT_SECONDS", 0)
    requests = []

    def handler(request):
        requests.append(str(request.url))
        if len(requests) == 1:
            return httpx.Response(503)
        return httpx.Response(200, text=STREAM, headers={"Content-Type": "text/event-stream"})

    calls = []
    done = asyncio.Event()

    def changed():
        calls.append(1)
        if len(calls) == 4:
            done.set()

    listener = asyncio.create_task(
        events.listen_for_changes(
            "https://staging.frikanalen.no/", changed, httpx.MockTransport(handler)
        )
    )
    await asyncio.wait_for(done.wait(), 2)
    listener.cancel()

    assert requests[0] == "https://staging.frikanalen.no/api/playout/events"
    # Refused once, then reconnected; every event asks for a reload.
    assert len(requests) >= 3
    assert len(calls) >= 4
