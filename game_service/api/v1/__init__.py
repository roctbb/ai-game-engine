import fastapi

app_v1 = fastapi.APIRouter()

@app_v1.get('/ping')
async def ping():
    return {
        'status': 'working',
    }
