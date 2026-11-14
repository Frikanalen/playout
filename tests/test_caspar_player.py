import asyncio

import pytest

from playout_lib import caspar_player
from playout_lib.caspar_player import CasparConnectionLost, CasparPlayer


def player_reading(data: bytes) -> CasparPlayer:
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    player = CasparPlayer()
    player.reader = reader
    return player


async def test_reads_a_single_line_201_reply():
    player = player_reading(b"201 VERSION OK\r\n2.5.0 N/A Stable\r\n")

    assert await player._get_response() == "2.5.0 N/A Stable\r\n"


async def test_reads_a_whole_xml_201_reply():
    # CasparCG 2.5 answers INFO <layer> this way: 201, then a multi-line
    # document ended by a blank line. All of it has to be consumed, or the
    # rest would be read as the next command's reply.
    xml = (
        b'<?xml version="1.0" encoding="utf-8"?>\r\n<channel>\r\n'
        + b"   <stage></stage>\r\n" * 200
        + b"</channel>\r\n\r\n"
    )
    player = player_reading(b"201 INFO OK\r\n" + xml)

    reply = await player._get_response()

    assert reply.startswith("<?xml") and reply.rstrip().endswith("</channel>")
    assert player.reader._buffer == b""


async def test_reads_an_info_reply_as_caspar_2_5_sends_it():
    # Captured from CasparCG 2.5: CRLF after the XML declaration, bare LF
    # inside the document, and "\n\r\n" at its end.
    xml = (
        b'<?xml version="1.0" encoding="utf-8"?>\r\n<channel>\n'
        + b"   <stage></stage>\n" * 200
        + b"</channel>\n\r\n"
    )
    player = player_reading(b"201 INFO OK\r\n" + xml)

    reply = await player._get_response()

    assert reply.startswith("<?xml") and reply.rstrip().endswith("</channel>")
    assert player.reader._buffer == b""


class FakeCaspar:
    """Just enough of an AMCP server: answers every command, can be killed."""

    def __init__(self):
        self.commands = []
        self.server = None
        self.writers = []

    async def start(self, port=0):
        self.server = await asyncio.start_server(self._serve, "127.0.0.1", port)
        return self.server.sockets[0].getsockname()[1]

    async def _serve(self, reader, writer):
        self.writers.append(writer)
        while line := await reader.readline():
            command = line.decode().strip()
            self.commands.append(command)
            if command == "INFO":
                writer.write(b"200 INFO OK\r\n1 720p5000 PLAYING\r\n\r\n")
            elif command == "VERSION":
                writer.write(b"201 VERSION OK\r\n2.5.0 N/A Stable\r\n")
            else:
                writer.write(b"202 " + command.split()[0].encode() + b" OK\r\n")
            await writer.drain()

    async def crash(self):
        self.server.close()
        for writer in self.writers:
            writer.close()
        await self.server.wait_closed()


@pytest.fixture
def fast(monkeypatch):
    monkeypatch.setattr(caspar_player, "CASPAR_HOST", "127.0.0.1")
    monkeypatch.setattr(caspar_player, "HEARTBEAT_INTERVAL", 0.05)
    monkeypatch.setattr(caspar_player, "CONNECT_RETRY_INTERVAL", 0.05)
    monkeypatch.setattr(caspar_player, "REPLY_TIMEOUT", 0.5)


async def connected(monkeypatch):
    caspar = FakeCaspar()
    monkeypatch.setattr(caspar_player, "CASPAR_PORT", await caspar.start())
    player = CasparPlayer()
    await player.connect()
    return caspar, player


async def test_notices_caspar_going_away_while_idle(fast, monkeypatch):
    # 2026-11-14: CasparCG crashed and nodm restarted it in a second, in the
    # middle of a long video. Nothing was sent until the next item, so the
    # channel stayed black until playout was restarted by hand.
    caspar, player = await connected(monkeypatch)

    await caspar.crash()

    await asyncio.wait_for(player.connection_lost.wait(), 1.0)


async def test_a_lost_connection_is_not_a_refused_command(fast, monkeypatch):
    # Items show the "unavailable" notice on ValueError; a dead connection
    # must not be mistaken for a missing file.
    caspar, player = await connected(monkeypatch)
    await caspar.crash()

    with pytest.raises(CasparConnectionLost):
        await player.issue('PLAY 1-50 "some/file"')
        await player.issue('PLAY 1-50 "some/file"')
    assert player.connection_lost.is_set()


async def test_a_silent_caspar_counts_as_lost(fast, monkeypatch):
    # A late reply would be read as the answer to the next command.
    player = CasparPlayer()
    player.reader = asyncio.StreamReader()
    player.writer = SilentWriter()

    with pytest.raises(CasparConnectionLost):
        await player.issue("VERSION")
    assert player.connection_lost.is_set()


async def test_nothing_is_sent_once_lost(fast, monkeypatch):
    caspar, player = await connected(monkeypatch)
    await caspar.crash()
    await asyncio.wait_for(player.connection_lost.wait(), 1.0)

    with pytest.raises(CasparConnectionLost):
        await player.issue("CLEAR 1-50")


async def test_waits_for_caspar_to_come_up(fast, monkeypatch):
    caspar = FakeCaspar()
    port = await caspar.start()
    await caspar.crash()  # nothing listens on port yet
    monkeypatch.setattr(caspar_player, "CASPAR_PORT", port)
    player = CasparPlayer()

    connecting = asyncio.create_task(player.connect())
    await asyncio.sleep(0.2)
    assert not connecting.done()
    await FakeCaspar().start(port)

    await asyncio.wait_for(connecting, 1.0)
    assert player.frame_rate == 50.0


class SilentWriter:
    def write(self, data):
        pass

    async def drain(self):
        pass
