"""Configuration constants and environment settings for the playout system."""

import os
from distutils.util import strtobool

# Layer definitions for CasparCG
VIDEO_LAYER = "1-50"
GRAPHICS_LAYER = "1-60"
CHANNELBUG_LAYER = "1-100"

# API endpoints
API_URL = os.environ.get("API_URL", "https://frikanalen.no/")

# File and media settings
FILE_BASE = ""
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
# Boost is held back so the true peak stays under this. We have gain, not a
# limiter, so the only way not to clip is not to turn it up that far.
LOUDNESS_TRUEPEAK_CEILING_DBTP = float(os.getenv("LOUDNESS_TRUEPEAK_CEILING_DBTP", "-1.0"))
