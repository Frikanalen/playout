"""Build screenbug_live_stortinget.png from the usual DIREKTE bug.

Stortinget's feed has a clock in the top right corner, at x 1162-1237,
y 43-55 of a 1280x720 frame. This lays the bug's own pill and logo out
around it: the pill exactly as wide as the clock, 6 px under it, and the
logo as tall as clock and pill together, 7 px to their left.

    python3 stills/make_stortinget.py screenbug_live.png stills/screenbug_live_stortinget.png

screenbug_live.png is CasparCG's stills/screenbug_live (1280x720 RGBA).
Needs Pillow.
"""

import sys

from PIL import Image

CLOCK = (1162, 43, 1237, 55)  # left, top, right, bottom of the digits
GAP_UNDER, GAP_LEFT = 6, 7
# In the usual still: what to cut out, and the solid part inside it.
PILL_CROP, PILL_SOLID = (1068, 44, 1169, 84), (1077, 52, 1162, 74)
LOGO_CROP, LOGO_SOLID = (1166, 34, 1216, 92), (1172, 41, 1209, 85)


def place(bug, crop, solid, target):
    """Scale crop so its solid part fills target's width; return it and where it goes."""
    scale = (target[2] - target[0]) / (solid[2] - solid[0])
    part = bug.crop(crop)
    part = part.resize((round(part.width * scale), round(part.height * scale)), Image.LANCZOS)
    x = target[0] - round((solid[0] - crop[0]) * scale)
    y = target[1] - round((solid[1] - crop[1]) * scale)
    return part, (x, y)


def main(source, out):
    bug = Image.open(source).convert("RGBA")
    left, top, right, bottom = CLOCK
    pill_top = bottom + GAP_UNDER
    pill_height = round((PILL_SOLID[3] - PILL_SOLID[1]) * (right - left + 1) / 85)
    pill_bottom = pill_top + pill_height
    logo_height = pill_bottom - top
    logo_width = round(37 * logo_height / 44)
    still = Image.new("RGBA", bug.size)
    for crop, solid, target in [
        (PILL_CROP, PILL_SOLID, (left, pill_top, right + 1, pill_bottom)),
        (LOGO_CROP, LOGO_SOLID, (left - GAP_LEFT - logo_width, top, left - GAP_LEFT, pill_bottom)),
    ]:
        part, at = place(bug, crop, solid, target)
        still.alpha_composite(part, at)
    still.save(out)


if __name__ == "__main__":
    main(*sys.argv[1:3])
