from pydantic import BaseModel

class BaseInfo(BaseModel):
    game: str
    players: int = 0
    is_started: bool = False

class HealthCheck(BaseModel):
    status: str

class BrowserInfo(BaseInfo):
    name: str
    max_players: int = 1

class TechnicalInfo(BaseInfo):
    current_step: int = 1
