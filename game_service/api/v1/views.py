import fastapi
from . import schemas

app_v1 = fastapi.APIRouter()

@app_v1.get('/ping')
async def health_check() -> schemas.HealthCheck:
    return {
        'status': 'working',
    }

@app_v1.get('/get_browser_info')
async def get_browser_info() -> schemas.BrowserInfo:
    return {
        'name': 'Steapin game',
        'game': 'tanks',
        'players': 2,
        'max_players': 12,
        'is_started': False,
    }

@app_v1.get('/get_technical_info')
async def get_technical_info() -> schemas.BrowserInfo:
    return {
        'current_step': 69,
        'game': 'tanks',
        'players': 2,
        'is_started': True,
    }

@app_v1.post('/stop_game')
async def stop_game() -> schemas.HealthCheck:
    return {
        'status': 'working',
    }