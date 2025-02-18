import fastapi
import api

app = fastapi.FastAPI()

@app.get('/ping')
async def ping():
    return {
        'status': 'running',
    }

app.include_router(
    api.v1.app_v1, 
    prefix='/api/v1',
    tags=['v1'],
)
