"""Health and readiness probes.

Two tiers, deliberately:

- `GET /api/health` — shallow. Is the API up, is the DB reachable, is a key
  configured. No outbound network, so the dashboard can poll it freely.
- `GET /api/health/{database,gcs,gemini,all}` — deep. Actually exercises each
  dependency (lists the bucket, calls the model). Costs a round trip, so it's
  for `verify-setup.bat` on a fresh machine, not for polling.

Everything returns 200 with a status field rather than an error code: a 503
from a probe is indistinguishable from "the server isn't listening yet", which
is the exact question the caller is trying to answer.
"""

import logging
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.db.session import engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])


def _probe(name: str, check) -> dict[str, Any]:
    """Runs one dependency check and normalizes success/failure into the same
    shape, so a caller can render results without special-casing."""
    try:
        return {"name": name, "status": "ok", "detail": check()}
    except Exception as exc:  # noqa: BLE001 - the failure IS the result here
        logger.warning("Health probe %s failed: %s", name, exc)
        return {"name": name, "status": "error", "detail": f"{type(exc).__name__}: {exc}"}


def _check_database() -> str:
    with engine.connect() as connection:
        name = connection.execute(text("SELECT current_database()")).scalar_one()
        calls = connection.execute(text("SELECT count(*) FROM calls")).scalar_one()
    return f"connected to '{name}', {calls} call(s) ingested"


def _check_gcs() -> str:
    from app.services import gcs_service

    settings = get_settings()
    blobs = gcs_service.list_audio_blobs()
    usable = sum(1 for b in blobs if (b.size_bytes or 0) >= settings.min_audio_bytes)
    return (
        f"bucket '{settings.gcs_bucket_name}' readable: {len(blobs)} audio object(s), "
        f"{usable} above the {settings.min_audio_bytes}-byte prescreen threshold"
    )


def _check_gemini() -> str:
    """Sends the smallest possible prompt. This costs a fraction of a cent and
    is the only way to distinguish a valid key from one that's expired, unbilled,
    or pointed at a retired model — all of which look fine in config."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in backend/.env")

    # Probes the extraction tier: it's the cheaper of the two, and it shares the
    # same key and endpoint as the transcription model, so a failure here means
    # the same thing for both. (See config for the two tiers.)
    model = settings.extraction_model
    llm = ChatGoogleGenerativeAI(
        model=model, google_api_key=settings.gemini_api_key, temperature=0
    )
    llm.invoke("Reply with the single word: ok")
    return f"model '{model}' responded"


@router.get("")
def health_check() -> dict[str, str]:
    """Shallow probe — safe to poll. Touches the DB but nothing over the network."""
    settings = get_settings()
    checks = {
        "status": "ok",
        "database": "ok",
        "gemini_api_key": "set" if settings.gemini_api_key else "missing",
        "gcs_bucket": settings.gcs_bucket_name or "missing",
        # Both tiers, since the pipeline is no longer one model (see
        # app/pipeline/kpi_registry.py): audio transcription runs on the
        # stronger one, every KPI node on the cheaper one.
        "model": f"{settings.gemini_transcription_model} (audio) + {settings.extraction_model} (kpi)",
    }

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - reported to the caller, not raised
        logger.warning("Health check: database unreachable: %s", exc)
        checks["database"] = f"error: {type(exc).__name__}: {exc}"
        checks["status"] = "degraded"

    if not settings.gemini_api_key:
        checks["status"] = "degraded"

    return checks


@router.get("/database")
def check_database() -> dict[str, Any]:
    return _probe("database", _check_database)


@router.get("/gcs")
def check_gcs() -> dict[str, Any]:
    return _probe("gcs", _check_gcs)


@router.get("/gemini")
def check_gemini() -> dict[str, Any]:
    return _probe("gemini", _check_gemini)


@router.get("/all")
def check_all() -> dict[str, Any]:
    """Everything at once — what the setup script calls to confirm a fresh
    machine is fully wired before anyone clicks Run Analysis."""
    probes = [
        _probe("database", _check_database),
        _probe("gcs", _check_gcs),
        _probe("gemini", _check_gemini),
    ]
    return {
        "status": "ok" if all(p["status"] == "ok" for p in probes) else "error",
        "probes": probes,
    }
