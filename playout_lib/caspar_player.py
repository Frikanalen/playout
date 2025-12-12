import asyncio
import logging
import sys

from playout_lib.config import CASPAR_HOST, CHANNELBUG_LAYER

logger = logging.getLogger(__name__)


class CasparPlayer:
    def __init__(self):
        self.reader = None
        self.writer = None
        self.caspar_lock = asyncio.Lock()

    async def _query_framerate(self):
        channels = await self.issue("INFO")

        if not isinstance(channels, list):
            raise ValueError("Expected multiline string from INFO command")

        channel_mode = channels[0].split(" ")[1]

        if len(channels) > 1:
            logger.warning(
                "This code assumes only 1 CasparCG. It will base "
                "calculations on the framerate of the first channel "
                f"(mode {channel_mode})."
            )

        if "i" in channel_mode:
            self.scan_mode = "interlaced"
        else:
            self.scan_mode = "progressive"

        self.scan_lines, self.frame_rate = [int(x) for x in channel_mode.split(self.scan_mode[0])]
        self.frame_rate = float(self.frame_rate / 100)

        logger.info(f"CasparCG mode: {channel_mode[:-2]}.{channel_mode[-2:]}")

    async def connect(self):
        """This code assumes that there is only one channel."""

        logger.info(f"Connecting to {CASPAR_HOST}")
        self.reader, self.writer = await asyncio.open_connection(CASPAR_HOST, 5250)
        await current_player.issue(f"PLAY {CHANNELBUG_LAYER} stills/screenbug")
        await self._query_framerate()

    async def _get_response(self):
        assert self.reader is not None, "Not connected to CasparCG"

        response = await asyncio.wait_for(self.reader.read(3), 10.0)

        try:
            return_code = int(response)
        except ValueError as e:
            raise ValueError("Did not receive numeric return code from CasparCG") from e

        while response[-2:] != b"\r\n":
            response += await self.reader.read(1)

        logger.debug(f"CasparCG replied {response.decode().strip()}")

        # From the AMCP spec:
        #
        # 200 [command] OK - The command has been executed and several lines of
        # data (seperated by \r\n) are being returned (terminated with an
        # additional \r\n)
        #
        # 201 [command] OK - The command has been executed and
        # data (terminated by \r\n) is being returned.
        #
        # 202 [command] OK - The command has been executed.

        if return_code == 200:  # multiline returned_data
            returned_data_buffer = b""

            while returned_data_buffer[-4:] != b"\r\n\r\n":
                returned_data_buffer += await self.reader.read(512)

            returned_data = returned_data_buffer.decode().splitlines()[:-1]

        elif return_code == 201:  # single-line returned_data
            returned_data = b""
            while returned_data[-2:] != b"\r\n":
                returned_data += await self.reader.read(512)

            returned_data = returned_data.decode()

        elif return_code == 202:  # no data returned
            returned_data = None

        else:
            raise ValueError("CasparCG command failed: " + response.decode().strip())

        return returned_data

    async def issue(self, cmd):
        assert self.writer is not None, "Not connected to CasparCG"

        """Issues a command to CasparCG. Blocks until a response is received."""
        async with self.caspar_lock:
            if self.writer.is_closing():
                logger.error("Connection closed!")
                sys.exit("Lost CasparCG connection")
            try:
                logger.debug("Issuing command to Caspar: %s", cmd.encode("utf-8"))
                self.writer.write((cmd + "\r\n").encode("utf-8"))
                await asyncio.wait_for(self.writer.drain(), 10)
                return await self._get_response()
            except TimeoutError:
                raise


# Global current player instance
current_player = CasparPlayer()
