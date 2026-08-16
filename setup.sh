#!/usr/bin/env bash
# Table for N — one-shot environment setup (safe to re-run any number of times).
#
# Cloud Shell / Vertex path (no API key):   ./setup.sh
# Laptop / AI Studio path:                  put GOOGLE_API_KEY in .env first,
#                                           then ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"

say()  { printf '\n\033[1m%s\033[0m\n' "$1"; }
tick() { printf '  ✓ %s\n' "$1"; }

say "Table for N · setup"

# ── 1 · python venv + deps ────────────────────────────────────────────
if [ ! -d .venv ]; then python3 -m venv .venv; fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --disable-pip-version-check \
  "google-adk[eval]==2.3.0" python-dotenv pydantic nest_asyncio uvicorn
tick "venv + google-adk[eval]==2.3.0"

# ── 2 · pick the auth path ────────────────────────────────────────────
KEY="$(grep -s '^GOOGLE_API_KEY=' .env | cut -d= -f2- || true)"
if [ -n "${KEY:-}" ] && [ "$KEY" != "YOUR_GOOGLE_API_KEY_HERE" ]; then
  MODE="aistudio"
  tick "auth: AI Studio key found in .env"
else
  MODE="vertex"
  PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
  if [ -z "$PROJECT" ]; then
    read -r -p "  Google Cloud project id: " PROJECT
    gcloud config set project "$PROJECT" -q
  fi
  gcloud services enable aiplatform.googleapis.com -q
  {
    echo "GOOGLE_GENAI_USE_VERTEXAI=True"
    echo "GOOGLE_CLOUD_PROJECT=$PROJECT"
    echo "GOOGLE_CLOUD_LOCATION=us-central1"
  } > .env
  tick "auth: Vertex AI on project $PROJECT (wrote .env, no API key anywhere)"
fi

# ── 3 · prebuild the felt table (single-port mode) ────────────────────
if command -v npm >/dev/null; then
  ( cd app && npm install --silent && npm run build --silent )
  tick "felt table built (app/out — the broadcast server serves it)"
else
  printf '  ⚠ npm not found — the felt table UI will be unavailable\n'
fi

# ── 4 · prove the model answers ───────────────────────────────────────
python - <<'PY'
import os
from dotenv import load_dotenv; load_dotenv(".env")
if os.environ.get("GOOGLE_API_KEY"):
    os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)
from google import genai
from google.genai import types as gt
client = genai.Client()
r = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Reply with exactly: table for N, ready to seat.",
    config=gt.GenerateContentConfig(
        thinking_config=gt.ThinkingConfig(thinking_budget=0), temperature=0.0))
print("  ✓ gemini-2.5-flash:", r.text.strip())
PY

say "Setup finished. Next:  source .venv/bin/activate  ·  ./verify.sh"
