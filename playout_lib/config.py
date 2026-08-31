"""Configuration constants and environment settings for the playout system."""

import os
from distutils.util import strtobool

# Layer definitions for CasparCG
VIDEO_LAYER = "1-50"
GRAPHICS_LAYER = "1-60"
CHANNELBUG_LAYER = "1-100"

# API endpoints
API_URL = os.environ.get("API_URL", "https://frikanalen.no/")
GRAPHICS_URL = os.environ.get("GRAPHICS_URL", "https://frikanalen.no/graphics/")

# File and media settings
#
# Leave MEDIA_ROOT empty for development, where CasparCG can load the URLs
# returned by the video-details API. Production uses the bare filenames from
# the videofiles API instead.
MEDIA_ROOT = os.environ.get("MEDIA_ROOT", "")


def media_location(location: str) -> str:
    """Normalize a bare filename for CasparCG's own AMCP-relative media path.

    CasparCG resolves PLAY/LOADBG filenames relative to its own configured
    <media-path>, so this must NOT be joined with a local mount path such as
    MEDIA_ROOT: doing so double-applies the media root (CasparCG then looks
    for <media-path>/<MEDIA_ROOT>/... and fails to find the file).
    """
    return location.lstrip("/")


CASPAR_HOST = os.environ["CASPAR_HOST"]
USE_ORIGINAL = strtobool(os.getenv("USE_ORIGINAL", "false"))

# Loudness normalization (EBU R128 / ITU-R BS.1770).
#
# The upload pipeline measures integrated loudness and true peak and stores
# them on the video file record. Files that have been measured are played
# back through a compensating gain; files that have not are played as-is.
LOUDNESS_NORMALIZATION = strtobool(os.getenv("LOUDNESS_NORMALIZATION", "true"))
LOUDNESS_TARGET_LUFS = float(os.getenv("LOUDNESS_TARGET_LUFS", "-23.0"))
# Cap on how much a quiet file may be lifted. Guards against a bogus
# measurement turning a near-silent file into a wall of amplified hiss.
LOUDNESS_MAX_BOOST_DB = float(os.getenv("LOUDNESS_MAX_BOOST_DB", "12.0"))
# Hard ceiling on the true peak of anything we play out. There is no limiter
# downstream, so gain is the only control we have: a file measured above this
# is turned down to it, and a quiet one is lifted only as far as it allows.
LOUDNESS_TRUEPEAK_CEILING_DBTP = float(os.getenv("LOUDNESS_TRUEPEAK_CEILING_DBTP", "-1.0"))
