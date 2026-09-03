from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

# backend/ — the directory holding .env, resolved from this file rather than
# the current working directory so it's found whether you launch uvicorn from
# backend/ or from the repo root.
BACKEND_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = BACKEND_ROOT / ".env"

# pydantic-settings feeds .env into the Settings object below, but it does NOT
# put those values into os.environ. Google's auth library reads
# GOOGLE_APPLICATION_CREDENTIALS straight from the process environment, so
# without this call that variable would be silently ignored when set in .env.
# (load_dotenv does not override variables already set in the real environment.)
load_dotenv(ENV_FILE)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # --- Google Cloud Storage (source of call recordings) ---
    gcp_project_id: str = ""
    gcs_bucket_name: str = "csdcallaudio"
    gcs_prefix: str = "recordings/"

    # --- Gemini Developer API (transcription + KPI/sentiment analysis in one call) ---
    # Audio bytes are downloaded from GCS and sent to Gemini inline — get a
    # key from Google AI Studio, this doesn't use Vertex AI / GCP project auth.
    gemini_api_key: str = ""
    # Two tiers, because the pipeline's two kinds of work have very different
    # difficulty and very different price tags (see app/pipeline/kpi_registry.py).
    #
    # TRANSCRIPTION runs once per recording, on the raw audio, and is the only
    # place a stronger model actually earns its cost: noisy call-center audio,
    # code-mixed Hindi/English, and everything downstream is built on whatever
    # it writes down. A transcription error is unrecoverable — no amount of
    # cleverness in a later node gets the words back.
    gemini_transcription_model: str = "gemini-3.5-flash"
    # EXTRACTION runs once per KPI node, on the transcript TEXT (no audio
    # tokens). Classifying an already-written transcript is a much easier task,
    # so it stays on the cheapest tier — which is what makes adding a KPI or
    # re-running one nearly free.
    #
    # NOTE: gemini-2.5-flash-lite (the original pin) is retired for new API
    # keys — it now 404s with "no longer available to new users". 3.5-flash-lite
    # is its direct replacement and the cheapest tier this key can call.
    gemini_extraction_model: str = "gemini-3.5-flash-lite"
    # Deprecated alias kept so an existing .env with GEMINI_MODEL=... keeps
    # working. Empty = "not set"; when set it overrides the extraction tier,
    # which is what that single setting used to drive.
    gemini_model: str = ""

    # --- Cost / throughput controls ---
    # Audio smaller than this can't contain meaningful speech (your bucket has
    # a number of 288-byte objects). They're marked rejected/corrupted by the
    # prescreen node without ever being downloaded or sent to Gemini, so they
    # cost nothing at all. Set to 0 to disable the gate.
    min_audio_bytes: int = 2048
    # Calls analyzed in parallel. Bounded because each in-flight call holds its
    # audio in memory and consumes Gemini quota; see the note in
    # ingest_pipeline about how this interacts with category convergence.
    analysis_concurrency: int = 4
    # Retries for transient model failures (429/503). Retrying in place is much
    # cheaper than failing the call and re-downloading + re-sending the audio
    # on the next pipeline run.
    analysis_max_retries: int = 3
    # Default cap on how many recordings one pipeline run may send to Gemini.
    # This is a spend guard, not a batch size: the bucket holds ~100 recordings
    # and the dashboard button is easy to click twice, so an uncapped default
    # would be a surprising bill. Prescreened-out objects are free and do NOT
    # count against it. 0 = no cap (process everything pending).
    # Overridable per request: POST /api/pipeline/run?limit=N.
    pipeline_run_limit: int = 5

    # --- Postgres (local instance) ---
    # Set as discrete fields so a password containing @ : / # or any other
    # URL-significant character just works — SQLAlchemy's URL.create escapes
    # them for us. Writing those characters into a connection string by hand
    # silently produces a wrong URL.
    db_user: str = "postgres"
    db_password: str = ""
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "csd_call_analysis"
    # Optional escape hatch: set this to a full connection string (e.g. a
    # managed/hosted database that hands you one) and it wins over the five
    # fields above.
    database_url: str = ""

    @property
    def extraction_model(self) -> str:
        """The cheap text tier, honouring the deprecated GEMINI_MODEL alias."""
        return self.gemini_model or self.gemini_extraction_model

    @property
    def sqlalchemy_url(self) -> URL | str:
        if self.database_url:
            return self.database_url
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.db_user,
            password=self.db_password or None,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )

    @property
    def libpq_dsn(self) -> str:
        """The same database, as a plain libpq connection string.

        LangGraph's PostgresSaver talks to psycopg directly rather than through
        SQLAlchemy, so it needs the URL without the `+psycopg` dialect suffix —
        passing SQLAlchemy's form to psycopg fails on the unknown scheme.
        `render_as_string(hide_password=False)` is what keeps a password
        containing URL-significant characters correctly escaped here, the same
        way `sqlalchemy_url` does for the ORM.
        """
        url = self.sqlalchemy_url
        if isinstance(url, str):
            return url.replace("postgresql+psycopg://", "postgresql://", 1)
        return url.set(drivername="postgresql").render_as_string(hide_password=False)

    # --- API / CORS (frontend dev server) ---
    cors_allow_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
