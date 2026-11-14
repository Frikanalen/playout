import asyncio

import main
from playout_lib import caspar_player

from .test_caspar_player import FakeCaspar, fast  # noqa: F401


class IdleScheduler:
    tasks: dict = {}

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


async def test_run_returns_when_the_watchdog_asks_for_a_restart(fast, monkeypatch):  # noqa: F811
    caspar = FakeCaspar()
    monkeypatch.setattr(caspar_player, "CASPAR_PORT", await caspar.start())
    monkeypatch.setattr(main, "current_player", caspar_player.CasparPlayer())
    monkeypatch.setattr(main, "Scheduler", IdleScheduler)

    class RestartingWatchdog:
        def __init__(self, scheduler, player):
            self.restart = asyncio.Event()

        async def run(self):
            await asyncio.sleep(0.1)
            self.restart.set()

    monkeypatch.setattr(main, "AirWatchdog", RestartingWatchdog)

    await asyncio.wait_for(main.Playout().run(), 1.0)
    await caspar.crash()


async def test_the_watchdog_can_be_switched_off(fast, monkeypatch):  # noqa: F811
    caspar = FakeCaspar()
    monkeypatch.setattr(caspar_player, "CASPAR_PORT", await caspar.start())
    monkeypatch.setattr(main, "current_player", caspar_player.CasparPlayer())
    monkeypatch.setattr(main, "Scheduler", IdleScheduler)
    monkeypatch.setattr(main, "AIR_WATCHDOG", False)

    running = asyncio.create_task(main.Playout().run())
    await asyncio.sleep(0.2)

    assert not any(c.startswith("INFO 1") for c in caspar.commands)
    running.cancel()
    await caspar.crash()
