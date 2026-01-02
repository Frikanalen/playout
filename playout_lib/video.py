import asyncio

from loguru import logger

from playout_lib.config import FILE_BASE, USE_ORIGINAL
from playout_lib.get_video_files import get_video_details
from playout_lib.items import PlannedItem, localtime


class PrerecordedVideo(PlannedItem):
    """A scheduled video file to be played."""

    def __init__(
        self,
        video_id,
        layer,
        framerate,
        start_time,
        end_time,
        video_details=None,
        video_files: dict[str, str] | None = None,
    ):
        """Initialize a PrerecordedVideo item.

        Args:
            video_id: The video ID
            layer: CasparCG layer
            framerate: Video framerate (will be divided by 1000)
            start_time: Scheduled start time
            end_time: Scheduled end time
            video_details: Optional pre-fetched Video object with complete details.
                          If not provided, will be lazily fetched on first access.
            video_files: Optional pre-fetched dict of format->filename mappings.
                        If not provided but video_details is, will be extracted from there.
        """
        super().__init__(layer, start_time, end_time)
        self.video_id = video_id
        self._video_details = video_details
        self._video_files = video_files
        self.framerate = float(framerate / 1000)
        self.metadata = None
        self.has_been_prepared = False
        self._filename: str | None = None

    @property
    def filename(self) -> str:
        """Get the filename to play. Determines which file to use based on USE_ORIGINAL setting.

        Returns:
            Full path to the video file to play
        """
        if self._filename is not None:
            return self._filename

        if self._video_files is None:
            logger.error(f"Video files not yet fetched for video {self.video_id}, using fallback")
            return FILE_BASE + "filler/FrikanalenLoop.avi"

        try:
            if USE_ORIGINAL:
                filename = self._video_files.get("original") or self._video_files.get("broadcast")
            else:
                filename = self._video_files.get("broadcast") or self._video_files.get("original")

            if filename:
                self._filename = FILE_BASE + filename
            else:
                logger.error(f"video {self.video_id} has no associated file!")
                self._filename = FILE_BASE + "filler/FrikanalenLoop.avi"

            return self._filename
        except Exception:
            logger.error(f"Error determining filename for video {self.video_id}")
            self._filename = FILE_BASE + "filler/FrikanalenLoop.avi"
            return self._filename

    async def ensure_files_loaded(self):
        """Ensure video details and files are fetched from the API."""
        if self._video_details is None and self._video_files is None:
            self._video_details = await get_video_details(self.video_id)
            if self._video_details:
                # Update framerate from fetched details
                self.framerate = float(self._video_details.framerate / 1000)
                self._video_files = self._video_details.files.additional_properties
            # Reset cached filename so property will recalculate
            self._filename = None

    async def prepare(self):
        """Preload the video file into CasparCG."""
        from .caspar_player import current_player

        try:
            seconds_since_start = (localtime() - self.start_time).total_seconds()
            if seconds_since_start > 2.0:
                self.has_been_prepared = False
                return

            cmd_string = (
                f'LOADBG {self.layer} "{self.filename}" "-filter:a aformat=sample_rates=48000"'
            )
            self.has_been_prepared = True
            await current_player.issue(cmd_string)
        except asyncio.CancelledError:
            pass

    async def cue(self):
        """Start playing the video."""
        from .caspar_player import current_player

        try:
            if self.has_been_prepared:
                cmd_string = f"PLAY {self.layer}"
            else:
                cmd_string = f'PLAY {self.layer} "{self.filename}"'
                cmd_string += ' "-filter:a aformat=sample_rates=48000"'
                cmd_string += " MIX 50 1 LINEAR RIGHT"

                seconds_since_start = (localtime() - self.start_time).total_seconds()
                if seconds_since_start > 2.0:
                    cmd_string += f" SEEK {int(current_player.frame_rate * seconds_since_start)}"

            await current_player.issue(cmd_string)
            await self._completion()
            print("I would have cleared here if it weren't for debugging")
            await current_player.issue(f"STOP {self.layer}")
            # await self.clear()
        except asyncio.CancelledError:
            logger.warning("asyncio.CancelledError, clearing layer...")
            print("I would have cleared here if it weren't for debugging")
            # await self.clear()

    def __repr__(self):
        time_range = f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
        title = "Video"
        if self._video_details and hasattr(self._video_details, "name"):
            title = f"Video: {self._video_details.name[:15]}..."
        return f"[{time_range} {title}]"
