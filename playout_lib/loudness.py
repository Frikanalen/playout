"""Playback gain derived from EBU R128 loudness measurements.

The API stores an integrated loudness and a true peak per video file, filled
in by the upload pipeline. When those are present we can play the file back
through a fixed gain that brings it to the house target instead of at
whatever level it was delivered at. Files nobody has measured are left alone.

There is no limiter anywhere downstream of playout, so the true peak ceiling
is a hard constraint rather than a preference: whatever loudness asks for,
the gain we return never puts a measured peak above it. Where the file has
no usable peak measurement we cannot make that promise, so we refuse to add
any gain at all rather than boost blind into a clip.
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

# Bounds beyond which a measurement is more likely broken than true, and acting
# on it would do more harm than ignoring it. Programme material does not average
# above 0 LUFS, and a file peaking 12 dB over full scale is a measurement fault,
# not a loud video -- obeying it literally would attenuate the programme into
# inaudibility. A few such records exist in the library.
MAX_PLAUSIBLE_INTEGRATED_LUFS = 0.0
MAX_PLAUSIBLE_TRUEPEAK_DBTP = 12.0


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
    if measured > MAX_PLAUSIBLE_INTEGRATED_LUFS:
        logger.warning(f"Loudness: ignoring implausible measurement of {measured:.2f} LUFS")
        return None

    peak = _as_measurement(truepeak_dbtp)
    if peak is not None and peak > MAX_PLAUSIBLE_TRUEPEAK_DBTP:
        logger.warning(
            f"Loudness: ignoring implausible true peak of {peak:.2f} dBTP, "
            f"treating the file as unmeasured for peak"
        )
        peak = None

    gain = min(target_lufs - measured, max_boost_db)

    if peak is None:
        # Nothing rules out this file already sitting at full scale, so the
        # most we can safely do is turn it down.
        return min(gain, 0.0)

    # One constraint, applied whichever way loudness wants to go: a file that
    # is already over the ceiling gets pulled down to it, and one that is quiet
    # but peaky is lifted only as far as its headroom allows.
    ceiling_gain = truepeak_ceiling_dbtp - peak
    if ceiling_gain < gain:
        logger.debug(
            f"Loudness: true peak {peak:.2f} dBTP allows {ceiling_gain:+.2f} dB, "
            f"holding back {gain:+.2f} dB"
        )
    return min(gain, ceiling_gain)


def db_to_multiplier(gain_db: float) -> float:
    """Convert a gain in dB to the linear sample multiplier CasparCG wants."""
    return 10 ** (gain_db / 20)
