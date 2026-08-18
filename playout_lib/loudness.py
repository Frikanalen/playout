"""Playback gain derived from EBU R128 loudness measurements.

The API stores an integrated loudness and a true peak per video file, filled
in by the upload pipeline. When those are present we can play the file back
through a fixed gain that brings it to the house target instead of at
whatever level it was delivered at. Files nobody has measured are left alone.
"""

import math

from loguru import logger

from .config import (
    LOUDNESS_MAX_BOOST_DB,
    LOUDNESS_TARGET_LUFS,
    LOUDNESS_TRUEPEAK_CEILING_DBTP,
)

# ffmpeg reports digital silence as -70 LUFS. Anything at or below that has no
# programme material to normalize, and pretending otherwise only amplifies
# whatever noise is in the file.
SILENCE_FLOOR_LUFS = -70.0


def _as_measurement(value) -> float | None:
    """Coerce an API field to a usable number, or None if it isn't one.

    The generated client hands back floats, None, or the Unset sentinel, and
    a measurement of infinity or NaN is as unusable as no measurement at all.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) else None


def playback_gain_db(
    integrated_lufs,
    truepeak_dbtp=None,
    *,
    target_lufs: float = LOUDNESS_TARGET_LUFS,
    max_boost_db: float = LOUDNESS_MAX_BOOST_DB,
    truepeak_ceiling_dbtp: float = LOUDNESS_TRUEPEAK_CEILING_DBTP,
) -> float | None:
    """Gain in dB that brings a measured file to the target loudness.

    Args:
        integrated_lufs: Measured integrated loudness of the file.
        truepeak_dbtp: Measured true peak, used to hold back boost that
                       would clip. Ignored when absent.

    Returns:
        The gain to apply, or None if the file has no usable measurement and
        should be played at its recorded level.
    """
    measured = _as_measurement(integrated_lufs)
    if measured is None or measured <= SILENCE_FLOOR_LUFS:
        return None

    gain = target_lufs - measured

    if gain > max_boost_db:
        logger.debug(
            f"Loudness: {measured:.2f} LUFS wants {gain:+.2f} dB, capped at {max_boost_db:+.2f} dB"
        )
        gain = max_boost_db

    # Attenuation can never clip, so the ceiling only ever holds back boost.
    peak = _as_measurement(truepeak_dbtp)
    if peak is not None and gain > 0:
        headroom = max(truepeak_ceiling_dbtp - peak, 0.0)
        if gain > headroom:
            logger.debug(
                f"Loudness: true peak {peak:.2f} dBTP leaves only "
                f"{headroom:+.2f} dB of headroom, holding back {gain:+.2f} dB"
            )
            gain = headroom

    return gain


def db_to_multiplier(gain_db: float) -> float:
    """Convert a gain in dB to the linear sample multiplier CasparCG wants."""
    return 10 ** (gain_db / 20)
