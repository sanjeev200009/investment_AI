# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers.auth import router as auth_router
from app.routers.stocks import router as stocks_router
from app.routers.portfolio import router as portfolio_router
from app.routers.chat import router as chat_router
from app.routers.notifications import router as notifications_router

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
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Include all routers with the prefix specified in config
for r in [auth_router, stocks_router, portfolio_router, chat_router, notifications_router]:
    app.include_router(
        r,
        prefix=f'/api/{settings.API_VERSION}'
    )

@app.get('/health')
def health_check():
    return {'status': 'ok', 'version': settings.API_VERSION}
