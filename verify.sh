#!/usr/bin/env bash
# Table for N — the rig check. Every tick is a real probe, not a guess.
set -uo pipefail
cd "$(dirname "$0")"

printf '\n\033[1mChecking the rig\033[0m\n\n'
fail=0
tick() { printf '  ✓ %-28s %s\n' "$1" "$2"; }
miss() { printf '  ✗ %-28s %s\n' "$1" "$2"; fail=1; }

V="$(uv run adk --version 2>/dev/null | head -1)" \
  && tick "adk installed" "$V" || miss "adk installed" "run ./setup.sh"

uv run python - <<'PY' 2>/dev/null && tick "adk 2 workflow apis" "Workflow + RequestInput" \
  || miss "adk 2 workflow apis" "wrong adk version — need 2.3.0"
from google.adk import Workflow
from google.adk.events import RequestInput
PY

if grep -qs '^GOOGLE_GENAI_USE_VERTEXAI=True' .env; then
  tick "auth mode" "Vertex AI — no API keys anywhere"
elif grep -qs '^GOOGLE_API_KEY=' .env && ! grep -qs 'YOUR_GOOGLE_API_KEY_HERE' .env; then
  tick "auth mode" "AI Studio key"
else
  miss "auth mode" "no .env — run ./setup.sh"
fi

uv run python - <<'PY' 2>/dev/null && tick "model answers" "gemini-2.5-flash" \
  || miss "model answers" "auth or project problem — re-run ./setup.sh"
import os
from dotenv import load_dotenv; load_dotenv(".env")
if os.environ.get("GOOGLE_API_KEY"):
    os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)
from google import genai
from google.genai import types as gt
client = genai.Client()
client.models.generate_content(model="gemini-2.5-flash", contents="ok",
    config=gt.GenerateContentConfig(
        thinking_config=gt.ThinkingConfig(thinking_budget=0)))
PY

uv run python scripts/verify_world.py >/dev/null 2>&1 \
  && tick "the world" "16 parties, every one has a perfect answer" \
  || miss "the world" "uv run python scripts/verify_world.py"

printf '\n'
if [ "$fail" -eq 0 ]; then printf 'Ready. Start with level 01.\n'; else printf 'Fix the ✗ lines above, then re-run ./verify.sh\n'; exit 1; fi
