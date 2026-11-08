"""Verified HTTPS context with a fallback for macOS Python installations."""
import os
import ssl
import sys
from pathlib import Path


def verified_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    # Python.org macOS builds can point at an uninstalled OpenSSL CA bundle.
    # Preserve explicitly configured trust stores and supplement missing defaults.
    if (sys.platform == "darwin" and not context.get_ca_certs()
            and not os.getenv("SSL_CERT_FILE") and not os.getenv("SSL_CERT_DIR")):
        bundle = Path("/etc/ssl/cert.pem")
        if bundle.is_file():
            context.load_verify_locations(cafile=str(bundle))
    return context
