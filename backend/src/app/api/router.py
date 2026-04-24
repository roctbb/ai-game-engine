from fastapi import APIRouter

from administration.api.router import router as administration_router
from antiplagiarism.api.router import router as antiplagiarism_router
from competition.api.router import router as competition_router
from app.api.health import router as health_router
from execution.api.router import router as execution_router
from game_catalog.api.router import progress_router as game_catalog_progress_router
from game_catalog.api.router import router as game_catalog_router
from identity.api.router import router as identity_router
from spectator_replay.api.router import router as spectator_replay_router
from team_workspace.api.router import router as team_workspace_router
from training_lobby.api.router import router as training_lobby_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(identity_router)
api_router.include_router(administration_router)
api_router.include_router(game_catalog_router)
api_router.include_router(game_catalog_progress_router)
api_router.include_router(team_workspace_router)
api_router.include_router(training_lobby_router)
api_router.include_router(competition_router)
api_router.include_router(antiplagiarism_router)
api_router.include_router(spectator_replay_router)
api_router.include_router(execution_router)
