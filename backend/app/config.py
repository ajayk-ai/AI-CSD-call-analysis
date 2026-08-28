from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Google Cloud Storage (source of call recordings) ---
    gcp_project_id: str = ""
    gcs_bucket_name: str = "csdcallaudio"
    gcs_prefix: str = "recordings/"

    # --- Gemini Developer API (transcription + KPI/sentiment analysis in one call) ---
    # Audio bytes are downloaded from GCS and sent to Gemini inline — get a
    # key from Google AI Studio, this doesn't use Vertex AI / GCP project auth.
    gemini_api_key: str = ""
    # Flash-Lite: cheapest and fastest tier, picked to optimize cost/latency
    # per your call. Bump to "gemini-2.5-flash" or "-pro" only if accuracy on
    # noisy call-center audio isn't good enough.
    gemini_model: str = "gemini-2.5-flash-lite"

    # --- Postgres ---
    # e.g. postgresql+psycopg://csd_app:password@localhost:5432/csd_call_analysis
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/csd_call_analysis"

    # --- API / CORS (frontend dev server) ---
    cors_allow_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
