# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, stocks, portfolio, chat, notifications

settings = get_settings()

app = FastAPI(
    title="InvestAI API",
    description="AI-powered investment assistant backend",
    version="1.0.0",
    docs_url=f"/api/{settings.API_VERSION}/docs",
    redoc_url=f"/api/{settings.API_VERSION}/redoc",
    openapi_url=f"/api/{settings.API_VERSION}/openapi.json",
)

# CORS — allow React Native / Expo dev client
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
PREFIX = f"/api/{settings.API_VERSION}"

app.include_router(auth.router,          prefix=f"{PREFIX}/auth",          tags=["Auth"])
app.include_router(stocks.router,        prefix=f"{PREFIX}/stocks",        tags=["Stocks"])
app.include_router(portfolio.router,     prefix=f"{PREFIX}/portfolio",     tags=["Portfolio"])
app.include_router(chat.router,          prefix=f"{PREFIX}/chat",          tags=["Chat"])
app.include_router(notifications.router, prefix=f"{PREFIX}/notifications", tags=["Notifications"])


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
