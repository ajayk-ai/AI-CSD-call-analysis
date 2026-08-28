import re
from dataclasses import dataclass

from google.cloud import storage

from app.config import get_settings

_AUDIO_EXTENSIONS = (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".mpeg", ".mpga")

_MIME_TYPES = {
    ".mp3": "audio/mp3",
    ".mpga": "audio/mp3",
    ".mpeg": "audio/mpeg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
}

# Matches "recordings/2026-08-24/BMCSTTA/<file>" -> ("2026-08-24", "BMCSTTA")
_PATH_PATTERN = re.compile(r"^.*?/(\d{4}-\d{2}-\d{2})/([^/]+)/[^/]+$")


@dataclass(frozen=True)
class AudioBlob:
    gcs_uri: str
    bucket_name: str
    object_name: str
    size_bytes: int | None
    recording_date: str | None
    team_code: str | None


def mime_type_for(object_name: str) -> str:
    lowered = object_name.lower()
    for ext, mime in _MIME_TYPES.items():
        if lowered.endswith(ext):
            return mime
    return "audio/mp3"


def _parse_path(object_name: str) -> tuple[str | None, str | None]:
    match = _PATH_PATTERN.match(object_name)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _get_client() -> storage.Client:
    settings = get_settings()
    return storage.Client(project=settings.gcp_project_id or None)


def list_audio_blobs(bucket_name: str | None = None, prefix: str | None = None) -> list[AudioBlob]:
    """Lists every audio object currently in the bucket under `prefix`.

    Diffing against what's already in Postgres (to find only the *new* ones)
    is the pipeline's job, not this function's — this just mirrors what's in
    GCS right now.
    """
    settings = get_settings()
    bucket_name = bucket_name or settings.gcs_bucket_name
    prefix = prefix if prefix is not None else settings.gcs_prefix

    client = _get_client()
    blobs = client.list_blobs(bucket_name, prefix=prefix)

    results: list[AudioBlob] = []
    for blob in blobs:
        if not blob.name.lower().endswith(_AUDIO_EXTENSIONS):
            continue
        recording_date, team_code = _parse_path(blob.name)
        results.append(
            AudioBlob(
                gcs_uri=f"gs://{bucket_name}/{blob.name}",
                bucket_name=bucket_name,
                object_name=blob.name,
                size_bytes=blob.size,
                recording_date=recording_date,
                team_code=team_code,
            )
        )
    return results


def download_blob_bytes(bucket_name: str, object_name: str) -> bytes:
    """Pulls one audio object's bytes down from GCS.

    We're on the API-key Gemini Developer API rather than Vertex AI, which
    means Gemini can't be pointed at a gs:// URI directly — the bytes have to
    come to us first, then get sent inline in the analysis request.
    """
    client = _get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)
    return blob.download_as_bytes()
