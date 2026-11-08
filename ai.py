"""ai.py - Everything DataSurge says out loud (Gemini).

Every function has a backup answer, so the app never freezes or crashes
if Gemini is busy (503) or slow.
"""
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL = "gemini-3.5-flash-lite"   # this one answered fast in our tests

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY"),
            http_options=types.HttpOptions(timeout=20_000),  # give up after 20 s
        )
    return _client


def _ask(prompt, backup):
    """Ask Gemini. If anything goes wrong, return the backup text instead."""
    try:
        response = _get_client().models.generate_content(model=MODEL, contents=prompt)
        text = (response.text or "").strip()
        return text if text else backup
    except Exception:
        return backup + "\n\n_(AI is busy right now, showing a basic summary.)_"


def explain_warning(w):
    """Plain-English explanation of ONE warning: what, why it matters, what to do."""
    prompt = f"""You are DataSurge, an AI teammate for a tired data center technician on night shift.
Explain this warning in 3 short bullet points:
- What is happening (plain English)
- Why it matters if ignored (what could break, and rough business impact)
- The first thing the technician should do

Warning: {w}
Keep it under 70 words. No jargon."""
    backup = (f"- **What:** {w['message']} at {w['location']} (reading: {w['value']}).\n"
              f"- **Why it matters:** level is **{w['level']}**, so it can grow if ignored.\n"
              f"- **Do first:** go check {w['location']} and log what you find.")
    return _ask(prompt, backup)


def shift_handoff(warnings):
    """Short briefing for the next shift: what happened, what's open, what to check first."""
    prompt = f"""You are DataSurge. Write a shift handoff note for the morning technician.
Use these sections with short bullets:
**Happened overnight**, **Still open (most urgent first)**, **Check first when you arrive**.
Mention small issues that could grow, not just the big ones.

Warnings: {warnings}
Keep it under 150 words."""
    open_ws = [w for w in warnings if w.get("status") != "resolved"]
    done_ws = [w for w in warnings if w.get("status") == "resolved"]
    lines = ["**Happened overnight**"]
    lines += [f"- Fixed: {w['message']} ({w['location']})" for w in done_ws] or ["- Nothing resolved yet"]
    lines.append("\n**Still open**")
    lines += [f"- [{w['level']}] {w['message']} ({w['location']})" for w in open_ws] or ["- Nothing open"]
    return _ask(prompt, "\n".join(lines))
