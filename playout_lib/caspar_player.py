import asyncio

from loguru import logger

from playout_lib.config import (
    CASPAR_HOST,
    CHANNELBUG,
    CHANNELBUG_LAYER,
    HTML_KEEPALIVE_LAYER,
    HTML_KEEPALIVE_URL,
)

# How long to wait for CasparCG to answer a command. A reply that comes later
# than this would be read as the answer to the next command, so a timeout is
# treated as a lost connection rather than a failed command.
REPLY_TIMEOUT = 10.0
# How often an idle connection is checked. During a long video nothing else
# talks to CasparCG, and a restarted server would otherwise go unnoticed until
# the next item, leaving the channel empty.
HEARTBEAT_INTERVAL = 2.0
# How often to try again while CasparCG does not accept connections.
CONNECT_RETRY_INTERVAL = 1.0
CASPAR_PORT = 5250


class CasparConnectionLost(ConnectionError):
    """The AMCP connection is gone, or can no longer be trusted.

    Not a ValueError on purpose: items take a ValueError to mean CasparCG
    refused a command (a missing file, say) and show a notice instead.
    """


class CasparPlayer:
    def __init__(self):
        self.reader = None
        self.writer = None
        self.caspar_lock = asyncio.Lock()
        # Set once the connection is lost. Nothing is sent after that: what
        # CasparCG plays has to be rebuilt from scratch, which a restart of
        # playout does (see main.py).
        self.connection_lost = asyncio.Event()
        self._heartbeat: asyncio.Task | None = None

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
        """Connect to CasparCG, waiting for as long as it takes to come up.

        This code assumes that there is only one channel.
        """
        attempt = 0
        while True:
            attempt += 1
            try:
                self.reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(CASPAR_HOST, CASPAR_PORT), REPLY_TIMEOUT
                )
                break
            except (OSError, TimeoutError) as error:
                # Log the first failure and then once a minute, not every second.
                if attempt == 1 or attempt % 60 == 0:
                    logger.error(f"Can't connect to CasparCG at {CASPAR_HOST} ({error!r})")
                await asyncio.sleep(CONNECT_RETRY_INTERVAL)
        logger.warning(f"Connected to CasparCG at {CASPAR_HOST}")
        await self.issue(f"PLAY {CHANNELBUG_LAYER} {CHANNELBUG}")
        await self._keep_html_alive()
        await self._query_framerate()
        self._heartbeat = asyncio.create_task(self._keep_checking())

    async def _keep_html_alive(self):
        """Keep one blank, transparent HTML page loaded (see HTML_KEEPALIVE_LAYER)."""
        if not HTML_KEEPALIVE_LAYER:
            return
        try:
            await self.issue(f"MIXER {HTML_KEEPALIVE_LAYER} OPACITY 0")
            await self.issue(f'PLAY {HTML_KEEPALIVE_LAYER} [HTML] "{HTML_KEEPALIVE_URL}"')
        except ValueError:
            # Only a mitigation: never let it keep playout off air.
            logger.exception("CasparCG refused the HTML keep-alive page")

    async def _keep_checking(self):
        """Ask CasparCG for its version every few seconds, to notice it going away."""
        try:
            while not self.connection_lost.is_set():
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await self.issue("VERSION", quiet=True)
        except CasparConnectionLost:
            pass

    def _lose(self, reason: str):
        if not self.connection_lost.is_set():
            logger.error(f"Lost the connection to CasparCG: {reason}")
            self.connection_lost.set()
        raise CasparConnectionLost(reason)

    async def _read(self, n):
        try:
            data = await asyncio.wait_for(self.reader.read(n), REPLY_TIMEOUT)
        except TimeoutError:
            self._lose(f"no reply within {REPLY_TIMEOUT:.0f} s")
        except OSError as error:
            self._lose(repr(error))
        if not data:
            self._lose("CasparCG closed the connection")
        return data

    async def _get_response(self, quiet=False):
        assert self.reader is not None, "Not connected to CasparCG"

        response = await self._read(3)
        # A short read: the code can arrive in pieces.
        while len(response) < 3:
            response += await self._read(3 - len(response))

        try:
            return_code = int(response)
        except ValueError:
            # Out of step with the protocol; nothing after this can be trusted.
            self._lose(f"expected a return code, got {response!r}")

        while response[-2:] != b"\r\n":
            response += await self._read(1)

        if not quiet:
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
                returned_data_buffer += await self._read(512)

            returned_data = returned_data_buffer.decode().splitlines()[:-1]

        elif return_code == 201:  # single-line returned_data
            returned_data = b""
            while returned_data[-2:] != b"\r\n":
                returned_data += await self._read(512)

            # CasparCG 2.5 answers INFO <layer> with 201 but a whole XML
            # document. Its lines end in a bare \n and the document in
            # "\n\r\n". Read all of it, or the rest would be taken for the
            # next command's reply.
            if returned_data.startswith(b"<?xml"):
                while returned_data[-3:] != b"\n\r\n":
                    returned_data += await self._read(512)

            returned_data = returned_data.decode()

        elif return_code == 202:  # no data returned
            returned_data = None

        else:
            raise ValueError("CasparCG command failed: " + response.decode().strip())

        return returned_data

    async def issue(self, cmd, log_as=None, quiet=False):
        """Issues a command to CasparCG. Blocks until a response is received.

        log_as replaces the command in the log, for commands carrying secrets.
        Raises CasparConnectionLost once the connection is gone.
        """
        assert self.writer is not None, "Not connected to CasparCG"

        async with self.caspar_lock:
            if self.connection_lost.is_set():
                raise CasparConnectionLost("already lost")
            if not quiet:
                logger.debug(f"Issuing command to Caspar: {log_as or cmd}")
            try:
                self.writer.write((cmd + "\r\n").encode("utf-8"))
                await asyncio.wait_for(self.writer.drain(), REPLY_TIMEOUT)
            except TimeoutError:
                self._lose(f"could not send within {REPLY_TIMEOUT:.0f} s")
            except OSError as error:
                self._lose(repr(error))
            return await self._get_response(quiet=quiet)


# Global current player instance
current_player = CasparPlayer()
