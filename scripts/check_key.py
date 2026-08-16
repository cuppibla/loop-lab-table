"""Prove your GOOGLE_API_KEY works — one real call, one clear verdict.

Run from the repo root:  uv run python scripts/check_key.py
"""
import os
import sys

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT, ".env"))

raw = os.environ.get("GOOGLE_API_KEY", "")
key = "".join(raw.split())  # strip stray whitespace/newlines from pasting

if not key or key == "YOUR_GOOGLE_API_KEY_HERE":
    sys.exit("❌ No key yet. Open .env at the repo root and replace "
             "YOUR_GOOGLE_API_KEY_HERE with your AI Studio key (starts with AIza…).")
if key != raw:
    print("⚠️  Your key had stray whitespace — stripped it for this check. "
          "Clean it up in .env too.")

os.environ["GOOGLE_API_KEY"] = key
if os.environ.get("GOOGLE_API_KEY"):
    # an AI Studio key wins locally; without one, Vertex mode is respected
    os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)

import logging
logging.getLogger("google_genai.models").setLevel(logging.ERROR)

from google import genai
from google.genai import types as gt

client = genai.Client(api_key=key)
try:
    reply = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Reply with exactly: table for N, ready to seat.",
        config=gt.GenerateContentConfig(
            thinking_config=gt.ThinkingConfig(thinking_budget=0), temperature=0.0),
    )
    print(f"🍽️  gemini-2.5-flash says: {reply.text.strip()}")
    print("✅ Key works — you're set for levels 01–05.")
except Exception as e:
    msg = str(e)
    if "API_KEY_INVALID" in msg or "API key not valid" in msg:
        sys.exit("❌ The key was rejected (API_KEY_INVALID). Re-copy it from "
                 "https://aistudio.google.com/app/apikey — the whole thing, ~40 chars.")
    sys.exit(f"❌ The call failed: {msg[:300]}")
