"""Diagnose Gemini without exposing credentials.

Run: backend/.venv/bin/python backend/check_gemini.py
"""
import asyncio
import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.request

from fastapi import HTTPException
from app.llm import _load_env_file
from app.tls import verified_context

HOST = "generativelanguage.googleapis.com"


def preflight():
    _load_env_file()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("FAIL configuration: GEMINI_API_KEY is missing from backend/.env.")
        return False
    print("PASS configuration: key present (hidden).")
    try:
        socket.getaddrinfo(HOST, 443)
    except OSError:
        print("FAIL DNS: cannot resolve Google. A new API key will not fix this. Check network/VPN/DNS.")
        return False
    print("PASS DNS: Google hostname resolves.")
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    try:
        with socket.create_connection((HOST, 443), timeout=10) as connection:
            with verified_context().wrap_socket(connection, server_hostname=HOST):
                pass
    except ssl.SSLError:
        print("FAIL TLS: certificate verification failed. Check the local trust store or HTTPS-inspecting proxy.")
        return False
    except OSError:
        print("FAIL connection: Google port 443 is unreachable. Check firewall/VPN/proxy.")
        return False
    print("PASS TLS: verified HTTPS connection.")
    # Read-only authentication check; no paid generation request yet.
    request = urllib.request.Request(
        f"https://{HOST}/v1beta/models/{model}",
        headers={"x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(request, timeout=15, context=verified_context()) as response:
            info = json.load(response)
    except urllib.error.HTTPError as error:
        reasons = {
            400: "request or key rejected; check the key and model in Google AI Studio",
            401: "authentication rejected; replace the key",
            403: "access denied; check key restrictions, project permissions, and region",
            404: "configured model is unavailable; select an available model in Google AI Studio and set GEMINI_MODEL",
            429: "quota exhausted or rate limited; check project quota/billing",
            503: "Google is overloaded; changing keys may not help",
        }
        print(f"FAIL model/auth HTTP {error.code}: {reasons.get(error.code, 'Google rejected the model lookup')}.")
        error.close()
        return False
    except (OSError, urllib.error.URLError):
        print("FAIL model lookup: request timed out or connection failed before generation.")
        return False
    if "generateContent" not in info.get("supportedGenerationMethods", []):
        print("FAIL model: this model does not support generateContent.")
        return False
    print(f"PASS authentication/model: {model} supports generateContent.")
    return True


async def main():
    if not preflight():
        return 1
    from app.main import assistant_check
    print("Testing a tiny generation request without simulation context…", flush=True)
    started = time.monotonic()
    try:
        result = await assistant_check()
        print(f"PASS generation via {result['model']} in {time.monotonic() - started:.1f}s: {result['answer']}")
        print("If chat still shows the old timeout message, the running backend has not loaded the latest code.")
        return 0
    except HTTPException as error:
        print(f"FAIL generation after {time.monotonic() - started:.1f}s ({error.status_code}): {error.detail}")
        print("Authentication/model lookup passed. This failure is in generation, not the simulation payload.")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
