"""Clear layers a previous playout left behind.

Each item clears its own layers when it ends or is cancelled, but only in
the process that played it. A playout that is restarted (a deploy, a pod
moved to another node, the watchdog's re-exec) starts from what the schedule
says should be on air now, and never sees the items its predecessor was
playing. Whatever those left on their layers stays on air underneath: on
2026-11-17 a live slot that had ended kept its SRT source decoding on 1-55
and the filler looping on 1-50 under the gap graphic, for as long as nobody
noticed, which starved caspar1 of CPU.

So once after startup, when the items that are on air have been cued, this
reads the channel and clears every playout-owned layer that holds something
none of them uses. It doesn't clear on connect: that would blank the
programme layer for a moment on every restart, where today a re-cue joins
the running video without a visible gap. The channel bug (1-100) is not
touched: playout sets it on connect.
"""

from xml.etree import ElementTree

from loguru import logger

from .config import (
    GRAPHICS_LAYER,
    LIVE_LAYER,
    NOTICE_LAYER,
    POSTER_LAYERS,
    STAFF_GRAPHIC_LAYERS,
    VIDEO_LAYER,
)


def graphic_layers(layer: str) -> set[str]:
    """A graphic's layer, its template sub-layer ("1-601") and music sub-layer ("1-602")."""
    return {layer, f"{layer}1", f"{layer}2"}


# Every layer playout puts something on, apart from the channel bug.
OWNED_LAYERS: frozenset[str] = frozenset(
    {VIDEO_LAYER, LIVE_LAYER}.union(
        *(
            graphic_layers(layer)
            for layer in (GRAPHICS_LAYER, NOTICE_LAYER, *POSTER_LAYERS, *STAFF_GRAPHIC_LAYERS)
        )
    )
)


def busy_layers(info, channel: int = 1) -> set[str]:
    """The layers ("1-55") with something in the foreground, from INFO 1's XML.

    CasparCG 2.5 answers INFO <layer> with the whole channel too, so one
    INFO 1 covers every layer. Raises ValueError if info isn't a channel
    state, so an unreadable answer is never taken for empty layers.
    """
    if not isinstance(info, str):
        raise ValueError(f"INFO returned {type(info).__name__}, not XML")
    root = ElementTree.fromstring(info.strip())
    layers = root.find("./stage/layer")
    if layers is None:
        raise ValueError("INFO returned no stage")
    busy = set()
    for element in layers:
        if not element.tag.startswith("layer_"):
            continue
        producer = (element.findtext("foreground/producer") or "").strip()
        if producer not in ("", "empty"):
            busy.add(f"{channel}-{element.tag.removeprefix('layer_')}")
    return busy


def layer_sort_key(layer: str) -> int:
    return int(layer.split("-")[1])


async def clear_stale_layers(player, in_use: set[str]) -> list[str]:
    """Clear the playout-owned layers that hold something no live item uses.

    in_use is the union of the layers of the items on air or about to be.
    Returns the layers cleared.
    """
    busy = busy_layers(await player.issue("INFO 1", quiet=True))
    stale = sorted((busy & OWNED_LAYERS) - in_use, key=layer_sort_key)
    if not stale:
        logger.info("No stale layers left by a previous playout")
        return []
    logger.info(f"Clearing layers a previous playout left on air: {', '.join(stale)}")
    for layer in stale:
        await player.issue(f"CLEAR {layer}")
        # Volume, opacity and the like stick to the layer: reset them too, or
        # the next item on it would inherit a hidden live layer's settings.
        await player.issue(f"MIXER {layer} CLEAR")
    return stale
