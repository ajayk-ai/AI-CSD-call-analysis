from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_calls, routes_dashboard, routes_pipeline
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="CSD Call Analysis Backend",
    description="Ingests call recordings from GCS, transcribes them, runs KPI/sentiment analysis via Gemini, and stores results in Postgres.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_pipeline.router)
app.include_router(routes_calls.router)
app.include_router(routes_dashboard.router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
