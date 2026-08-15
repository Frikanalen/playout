import os

# playout_lib.config reads CASPAR_HOST at import time and raises if unset.
# Set a dummy value before any test module imports playout_lib.
os.environ.setdefault("CASPAR_HOST", "test-caspar-host")
