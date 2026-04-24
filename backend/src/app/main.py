from fastapi import FastAPI

from app.api.router import api_router
from shared.api.errors import install_exception_handlers
from shared.config.settings import settings

app = FastAPI(title=settings.app_name, debug=settings.debug)
install_exception_handlers(app)
app.include_router(api_router, prefix="/api/v1")
