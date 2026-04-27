from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress

from app.dependencies import get_container
from shared.config.settings import settings

logger = logging.getLogger(__name__)


async def run_matchmaker_loop(stop_event: asyncio.Event) -> None:
    interval = max(settings.training_lobby_auto_matchmaking_interval_seconds, 0.25)
    logger.info("Training lobby matchmaker loop started with interval %.2fs", interval)
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(get_container().training_lobby.run_due_matchmaking_cycles)
        except Exception:
            logger.exception("Training lobby matchmaker tick failed")
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
    logger.info("Training lobby matchmaker loop stopped")


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not settings.training_lobby_auto_matchmaking_enabled:
        logger.warning("TRAINING_LOBBY_AUTO_MATCHMAKING_ENABLED is false; matchmaker exits")
        return

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)
    await run_matchmaker_loop(stop_event)


if __name__ == "__main__":
    asyncio.run(main())
