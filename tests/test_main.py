import asyncio

import main
from playout_lib import caspar_player

from .test_caspar_player import FakeCaspar, fast  # noqa: F401


class IdleScheduler:
    async def run(self):
        await asyncio.Event().wait()


async def test_run_returns_when_caspar_is_lost(fast, monkeypatch):  # noqa: F811
    # main() then exits non-zero, and the restarted container cues whatever
    # should be on air by then.
    caspar = FakeCaspar()
    monkeypatch.setattr(caspar_player, "CASPAR_PORT", await caspar.start())
    player = caspar_player.CasparPlayer()
    monkeypatch.setattr(main, "current_player", player)
    monkeypatch.setattr(main, "Scheduler", IdleScheduler)

    running = asyncio.create_task(main.Playout().run())
    await asyncio.sleep(0.1)
    assert not running.done()
    await caspar.crash()

    await asyncio.wait_for(running, 1.0)
