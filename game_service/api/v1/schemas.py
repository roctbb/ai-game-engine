from pydantic import BaseModel

class BaseInfo(BaseModel):
    game: str
    players: int
    is_started: bool

class HealthCheck(BaseModel):
    status: str

class BrowserInfo(BaseInfo):
    name: str
    max_players: int

class TechnicalInfo(BaseInfo):
    current_step: int
