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
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers with the prefix specified in config
for r in [auth_router, stocks_router, portfolio_router, chat_router, notifications_router]:
    app.include_router(
        r,
        prefix=f'/api/{settings.API_VERSION}'
    )

# --- SWAGGER CDN PATCH ---
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui-bundle.js",
        swagger_css_url="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui.css",
    )

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="https://cdnjs.cloudflare.com/ajax/libs/redoc/2.1.3/redoc.standalone.min.js",
    )
# -------------------------

@app.get('/health')
def health_check():
    return {'status': 'ok', 'version': settings.API_VERSION}
