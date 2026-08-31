"""Package init — kept deliberately tiny, but it is the earliest code that
runs for every entry point (uvicorn, alembic, pytest), which is exactly what
the SSL setup below needs.

Python's HTTPS stack normally trusts only the CA bundle shipped by `certifi`.
On a network that does TLS inspection (a corporate proxy re-signing traffic
with its own root CA), that bundle has no idea about the proxy's certificate,
so every outbound HTTPS call — Gemini, Google Cloud Storage — fails with
"self-signed certificate in certificate chain" or "unable to get local issuer
certificate". The proxy's root CA *is* installed in the OS certificate store,
because that's how the browser and the rest of the machine trust it.

`truststore` points Python at that OS store instead of the certifi bundle, so
the same certificates the OS already trusts are trusted here too. It must be
injected before anything constructs an ssl.SSLContext, hence its position at
the very top of the package.
"""

import logging

logger = logging.getLogger(__name__)

try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # noqa: BLE001 - never let TLS setup break startup outright
    # Not fatal: on a network without TLS inspection the default certifi
    # bundle works fine. Logged so that a later SSL error is easy to connect
    # back to this.
    logger.warning("Could not enable the OS certificate store; falling back to certifi.", exc_info=True)
