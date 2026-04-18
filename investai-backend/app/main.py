# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, stocks, portfolio, chat, notifications

settings = get_settings()

app = FastAPI(
    title='InvestAI API',
    version=settings.API_VERSION,
    description='AI-powered investment platform for CSE stocks',
    docs_url='/docs',
    redoc_url='/redoc',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],  # Tighten in production
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Include all routers with the prefix specified in config
for router_module in [auth, stocks, portfolio, chat, notifications]:
    app.include_router(
        router_module.router,
        prefix=f'/api/{settings.API_VERSION}'
    )

@app.get('/health')
def health_check():
    return {'status': 'ok', 'version': settings.API_VERSION}
