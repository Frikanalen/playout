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
