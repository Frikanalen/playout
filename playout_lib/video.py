import asyncio

from loguru import logger

from playout_lib.config import (
    FILE_BASE,
    LOUDNESS_NORMALIZATION,
    MEDIA_ROOT,
    USE_ORIGINAL,
    media_location,
)
from playout_lib.get_video_files import get_video_details, get_video_file_records
from playout_lib.items import PlannedItem, localtime
from playout_lib.loudness import db_to_multiplier, playback_gain_db


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
        video_file_records: dict | None = None,
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
            video_files: Optional pre-fetched dict of variant->filename mappings.
                        If not provided but video_details is, will be extracted from there.
            video_file_records: Optional pre-fetched dict of variant->VideoFile, carrying
                        the loudness measurements. Absent means play unnormalized.
        """
        super().__init__(layer, start_time, end_time)
        self.video_id = video_id
        self._video_details = video_details
        self._video_files = video_files
        self._video_file_records = video_file_records
        self.framerate = float(framerate / 1000)
        self.metadata = None
        self.has_been_prepared = False
        self._filename: str | None = None
        self._variant: str | None = None

    def _resolve_file(self) -> tuple[str | None, str]:
        """Pick the file to play, honouring the USE_ORIGINAL setting.

        Returns:
            (variant, path) for the chosen file, or (None, filler) when there
            is nothing to play. The variant is what the loudness measurement
            has to be looked up under, so the two are resolved together.
        """
        if self._filename is not None:
            return self._variant, self._filename

        fallback = FILE_BASE + "filler/FrikanalenLoop.avi"

        if self._video_files is None and not self._video_file_records:
            logger.error(f"Video files not yet fetched for video {self.video_id}, using fallback")
            return None, fallback

        try:
            preferred = ("original", "broadcast") if USE_ORIGINAL else ("broadcast", "original")

            # The videofiles endpoint supplies bare filenames. In production,
            # prefer those records and put the chosen filename under the media
            # mount. Development keeps using the HTTP URLs from video details.
            records = self._video_file_records or {}
            if MEDIA_ROOT and records:
                variant = next((v for v in preferred if records.get(v)), None)
                location = media_location(records[variant].filename) if variant else None
            else:
                files = self._video_files or {}
                variant = next((v for v in preferred if files.get(v)), None)
                location = files.get(variant) if variant else None

            if variant is not None and location:
                self._variant = variant
                self._filename = location
            else:
                logger.error(f"video {self.video_id} has no associated file!")
                self._filename = fallback
        except Exception:
            logger.error(f"Error determining filename for video {self.video_id}")
            self._variant = None
            self._filename = fallback

        return self._variant, self._filename

    @property
    def filename(self) -> str:
        """Get the filename to play. Determines which file to use based on USE_ORIGINAL setting.

        Returns:
            Full path to the video file to play
        """
        return self._resolve_file()[1]

    @property
    def gain_db(self) -> float | None:
        """Loudness correction for the file we are about to play, in dB.

        Returns:
            The gain to apply, or None when the file carries no usable
            measurement and should go out at its recorded level.
        """
        if not LOUDNESS_NORMALIZATION:
            return None

        variant, _ = self._resolve_file()
        if variant is None or not self._video_file_records:
            return None

        record = self._video_file_records.get(variant)
        if record is None:
            return None

        return playback_gain_db(record.integrated_lufs, record.truepeak_lufs)

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
            self._variant = None

        if self._video_file_records is None:
            # Loudness is a nicety; a video that plays at its recorded level
            # is much better than a video that does not play at all.
            try:
                self._video_file_records = await get_video_file_records(self.video_id)
            except Exception as error:
                logger.warning(
                    f"Could not fetch file records for video {self.video_id} "
                    f"({error}), playing it unnormalized"
                )
                self._video_file_records = {}

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

            await self._set_playback_volume()
            await current_player.issue(cmd_string)
            await self._completion()
            print("I would have cleared here if it weren't for debugging")
            await current_player.issue(f"STOP {self.layer}")
            # await self.clear()
        except asyncio.CancelledError:
            logger.warning("asyncio.CancelledError, clearing layer...")
            print("I would have cleared here if it weren't for debugging")
            # await self.clear()

    async def _set_playback_volume(self):
        """Set the layer volume for this file just before it goes to air.

        The mixer setting sticks to the layer, so an unmeasured file has to
        actively reset it to unity rather than inherit the last item's gain.
        The command is issued at cue time, not at prepare time, so it cannot
        land on the outgoing video still playing on this layer.
        """
        from .caspar_player import current_player

        gain_db = self.gain_db
        if gain_db is None:
            volume = 1.0
            logger.debug(f"No usable loudness measurement for video {self.video_id}, playing as-is")
        else:
            volume = db_to_multiplier(gain_db)
            logger.info(
                f"Loudness: playing video {self.video_id} at {gain_db:+.2f} dB "
                f"(volume {volume:.4f})"
            )

        await current_player.issue(f"MIXER {self.layer} VOLUME {volume:.4f}")

    def __repr__(self):
        time_range = f"{self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}"
        title = "Video"
        if self._video_details and hasattr(self._video_details, "name"):
            title = f"Video: {self._video_details.name[:15]}..."
        return f"[{time_range} {title}]"
