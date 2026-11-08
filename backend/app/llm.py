"""Claude API wrapper. Reads ANTHROPIC_API_KEY from the environment (or
backend/.env). If no credentials are present, or a call fails, callers fall
back to template-based text so the demo works offline."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import anthropic

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _load_env_file():
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class LLM:
    def __init__(self):
        _load_env_file()
        self.model = os.getenv("DATASURGE_MODEL", "claude-opus-5-5")
        self.effort = os.getenv("DATASURGE_EFFORT", "low")
        disabled = os.getenv("DATASURGE_LLM", "on").lower() == "off"
        has_cred = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))
        self.client: Optional[anthropic.AsyncAnthropic] = (
            anthropic.AsyncAnthropic(timeout=90.0, max_retries=1) if has_cred and not disabled else None
        )
        self.last_error: Optional[str] = None if self.client else (
            "disabled (DATASURGE_LLM=off)" if disabled else "no ANTHROPIC_API_KEY set — using templates")

    @property
    def available(self) -> bool:
        return self.client is not None

    def status(self) -> dict:
        return {"available": self.available, "model": self.model, "last_error": self.last_error}

    async def complete(self, system: str, prompt: str, max_tokens: int = 4000) -> Optional[str]:
        """Return Claude's text, or None if unavailable/failed (caller uses template)."""
        if not self.client:
            return None
        try:
            resp = await self.client.beta.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_config={"effort": self.effort},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.AuthenticationError:
            self.last_error = "invalid API key"
            return None
        except anthropic.RateLimitError:
            self.last_error = "rate limited"
            return None
        except anthropic.APIStatusError as e:
            self.last_error = f"API error {e.status_code}"
            return None
        except anthropic.APIConnectionError:
            self.last_error = "network error (offline?)"
            return None
        if resp.stop_reason == "refusal":
            self.last_error = "model declined the request"
            return None
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text:
            self.last_error = "empty response"
            return None
        self.last_error = None
        return text
