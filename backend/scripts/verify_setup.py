"""Check that this machine can reach everything the pipeline needs.

Run via `verify-setup.bat`, or directly:

    cd backend && uv run python scripts/verify_setup.py

Exercises Postgres, the GCS bucket and the Gemini API for real, so a broken
machine reports which dependency is broken instead of "Run Analysis did
nothing". Exits non-zero if any probe fails.

The Gemini probe sends one tiny prompt (a fraction of a cent). That is the
point: a key can be present and syntactically valid while still being expired,
unbilled, or pointed at a model that has since been retired — none of which is
visible from config alone.
"""

import logging
import sys
import warnings
from pathlib import Path

# Running this as `python scripts/verify_setup.py` puts scripts/ on sys.path,
# not backend/, so `app` would not be importable. Add the backend root
# explicitly rather than requiring the caller to set PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Third-party chatter would bury the three lines that matter. Silenced before
# importing anything that emits it.
warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

from app.api.routes_health import _check_database, _check_gcs, _check_gemini, _probe  # noqa: E402

PROBES = [
    ("database", _check_database),
    ("gcs", _check_gcs),
    ("gemini", _check_gemini),
]


def main() -> int:
    failed = False
    for name, check in PROBES:
        result = _probe(name, check)
        ok = result["status"] == "ok"
        failed = failed or not ok
        print(f"{'[OK] ' if ok else '[X]  '} {name}: {result['detail']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
