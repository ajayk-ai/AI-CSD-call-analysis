import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import routes_calls, routes_dashboard, routes_health, routes_pipeline
from app.config import get_settings

logger = logging.getLogger(__name__)

# backend/ and frontend/ are sibling directories in this repo, so this is
# resolved from THIS file rather than the working directory — it's correct
# whether uvicorn is launched from backend/ or from the repo root.
_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

settings = get_settings()

app = FastAPI(
    title="CSD Call Analysis Backend",
    description="Ingests call recordings from GCS, transcribes them, runs KPI/sentiment analysis via Gemini, and stores results in Postgres.",
    version="0.1.0",
)


# --- Middleware ---------------------------------------------------------
# ORDER MATTERS. add_middleware() inserts at the front of the stack, so the
# LAST one registered ends up OUTERMOST. The error catcher is registered
# first and CORS second, which yields:
#
#     CORSMiddleware  ->  catch_unhandled_errors  ->  routes
#
# so the catcher's response travels back out through CORS and picks up the
# Access-Control-Allow-Origin header.
#
# A @app.exception_handler(Exception) does NOT work for this: Starlette
# special-cases the catch-all handler onto ServerErrorMiddleware, which sits
# OUTSIDE CORSMiddleware. Its 500 therefore carries no CORS header, the
# browser reports a misleading "blocked by CORS policy", and the real error
# (a TLS failure, in the case that prompted this) stays invisible.


@app.middleware("http")
async def catch_unhandled_errors(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    try:
        return await call_next(request)
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all boundary
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": f"{type(exc).__name__}: {exc}"},
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# routes_health owns both the shallow GET /api/health (safe to poll) and the
# deep GET /api/health/{database,gcs,gemini,all} probes that actually exercise
# each dependency — see that module's docstring for why they're separate.
app.include_router(routes_health.router)
app.include_router(routes_pipeline.router)
app.include_router(routes_calls.router)
app.include_router(routes_dashboard.router)

# --- Frontend (production build, served from this same process) --------
# Mounted LAST and at "/" so it acts as a catch-all: FastAPI tries the routers
# above first (everything real lives under /api/...), and only a path that
# matches none of them falls through to a static file. html=True serves
# index.html for "/" (and any other directory-style request) — sufficient
# here since the dashboard is a single page with no client-side routing, so
# "/" is the only path a browser navigation ever requests.
#
# This is optional: if the frontend hasn't been built yet (no frontend/dist),
# this backend still serves the API alone — the two-process dev setup
# (`npm run dev` on :5173 talking to this on :8000 via CORS) still works
# exactly as before. Build it with `npm run build` in frontend/ to enable
# single-process serving from this port instead.
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
else:
    logger.info(
        "frontend/dist not found (%s) — serving API only. Run `npm run build` in "
        "frontend/ to also serve the dashboard from this port.",
        _FRONTEND_DIST,
    )
