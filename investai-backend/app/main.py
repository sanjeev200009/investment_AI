# app/main.py
import logging
import os
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings

# Without a handler every logger.info in the app (including the latency lines
# below) was silently dropped under uvicorn.
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("investai.request")

IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() == "production"

from app.routers.stocks import router as stocks_router
from app.routers.portfolio import router as portfolio_router
from app.routers.chat import router as chat_router
from app.routers.notifications import router as notifications_router
from app.routers.dashboard import router as dashboard_router
from app.routers.user import router as user_router
from app.routers.auth import router as auth_router
from app.routers.watchlist import router as watchlist_router
from app.routers.rules import router as rules_router
from app.routers.recommendations import router as recommendations_router
from app.routers.device import router as device_router
from app.routers.learn import router as learn_router

settings = get_settings()

app = FastAPI(
    title='InvestAI API',
    version=settings.API_VERSION,
    description='AI-powered investment platform for CSE stocks',
    docs_url=None,
    redoc_url=None,
    # The schema maps every endpoint; keep it off the public production API.
    openapi_url=None if IS_PRODUCTION else '/openapi.json',
)

app.add_middleware(
    CORSMiddleware,
    # Deploy-time allow-list from CORS_ORIGINS (I-22 / deployment hardening).
    # A public API keeps the wildcard only in the sense that *some* default
    # must exist; the value is one config setting away from a pinned origin.
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    # allow_credentials=True alongside a wildcard origin is a combination the
    # CORS spec forbids and browsers reject: a credentialed request requires the
    # server to echo one specific origin, which "*" cannot. This app authenticates
    # with bearer tokens in the Authorization header — never cookies — so no
    # request it makes needs the credentials flag, and the web target named in
    # NFR-Portability works again. (I-22.) If a cookie-based web client is ever
    # added, enumerate its origins explicitly here rather than re-enabling the
    # wildcard.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request-latency instrumentation (I-17) ─────────────────────────────────
#
# §13 of the dissertation commits to "Response Time < 3-5 seconds" and there was
# no instrumentation to produce a single number for it. One log line per
# request, in a parseable key=value form, is the cheapest durable artifact: it
# can be grepped for a percentile at write-up time (`investai.request` logger,
# duration_ms), shipped into any log analyser, or tallied live during a demo.
# The chat endpoints are the ones the metric names, but every route is logged
# because "performance" claims never stay scoped to the route you planned.

@app.middleware("http")
async def log_request_latency(request: Request, call_next):
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.error(
            'path="%s" method=%s status=500 duration_ms=%d event=exception',
            request.url.path, request.method, duration_ms)
        raise
    duration_ms = int((time.monotonic() - start) * 1000)
    # Streaming responses (POST /chat/stream) complete the middleware when the
    # *headers* are sent, so this measures time-to-first-byte there — which is
    # the honest number for the NFR anyway: it is what the user experiences as
    # "the app started answering".
    logger.info(
        'path="%s" method=%s status=%d duration_ms=%d',
        request.url.path, request.method, response.status_code, duration_ms)
    response.headers["x-response-time-ms"] = str(duration_ms)
    return response

# Include all routers with the prefix specified in config
for r in [auth_router, stocks_router, portfolio_router, chat_router, notifications_router, dashboard_router, user_router, watchlist_router, rules_router, recommendations_router, device_router, learn_router]:
    app.include_router(
        r,
        prefix=f'/api/{settings.API_VERSION}'
    )

# --- SWAGGER CDN PATCH ---
# docs_url=None plus these routes is deliberate: FastAPI's default Swagger assets
# come from a CDN that was unreachable during development, so the UI is served
# from cdnjs instead. Development only.
if not IS_PRODUCTION:
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
    """Liveness plus a database round trip, so the platform restarts a worker
    whose database connection is dead instead of routing traffic to it."""
    from fastapi.responses import JSONResponse
    from sqlalchemy import text
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        db.execute(text('SELECT 1'))
    except Exception as exc:
        logging.getLogger(__name__).error('Health check DB failure: %s', exc)
        return JSONResponse(status_code=503, content={'status': 'degraded', 'database': 'unreachable'})
    finally:
        db.close()
    return {'status': 'ok', 'version': settings.API_VERSION, 'database': 'ok'}
