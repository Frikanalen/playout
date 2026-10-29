import asyncio

from playout_lib.caspar_player import CasparPlayer


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
