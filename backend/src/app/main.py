import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api.router import api_router
from app.dependencies import get_container
from shared.api.errors import install_exception_handlers
from shared.config.settings import settings

logger = logging.getLogger(__name__)
_matchmaking_task: asyncio.Task[None] | None = None


async def start_training_lobby_matchmaking_loop() -> None:
    global _matchmaking_task
    if not settings.training_lobby_auto_matchmaking_enabled:
        return
    if _matchmaking_task is not None and not _matchmaking_task.done():
        return
    _matchmaking_task = asyncio.create_task(_training_lobby_matchmaking_loop())


async def stop_training_lobby_matchmaking_loop() -> None:
    global _matchmaking_task
    if _matchmaking_task is None:
        return
    _matchmaking_task.cancel()
    with suppress(asyncio.CancelledError):
        await _matchmaking_task
    _matchmaking_task = None


async def _training_lobby_matchmaking_loop() -> None:
    interval = max(settings.training_lobby_auto_matchmaking_interval_seconds, 0.25)
    while True:
        try:
            await asyncio.to_thread(get_container().training_lobby.run_due_matchmaking_cycles)
        except Exception:
            logger.exception("Training lobby auto-matchmaking tick failed")
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await start_training_lobby_matchmaking_loop()
    try:
        yield
    finally:
        await stop_training_lobby_matchmaking_loop()


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
install_exception_handlers(app)
app.include_router(api_router, prefix="/api/v1")
