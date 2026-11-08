"""Bounded retries for temporary Gemini service failures."""
import json
import time
import urllib.error
import urllib.request

from .tls import verified_context


def generate(request, attempts=3):
    context = verified_context()
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=60, context=context) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code not in (502, 503, 504) or attempt == attempts - 1:
                raise
            error.close()
            time.sleep(2 ** attempt)
        except (TimeoutError, urllib.error.URLError) as error:
            timeout = isinstance(error, TimeoutError) or isinstance(getattr(error, "reason", None), TimeoutError)
            if not timeout:
                raise
            if attempt >= min(1, attempts - 1):
                raise TimeoutError("Gemini response timed out") from error
            time.sleep(1)
