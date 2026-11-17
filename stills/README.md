# Bug stills

Stills playout puts on the bug layer (`CHANNELBUG_LAYER`) that are not the
usual `stills/screenbug` and `stills/screenbug_live`. CasparCG loads them
from `stills/` in its media path, so copy a new one there on every CasparCG
host (caspar-sw1 for staging, caspar1 for prod) before a release that uses it.

- `screenbug_live_stortinget.png`: DIREKTE under the clock in Stortinget's
  feed, the logo to its left (`logoPosition: stortinget-clock`). Built by
  `make_stortinget.py` from `screenbug_live`.
