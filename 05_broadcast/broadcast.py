"""The broadcast server for Table for N — COMPLETE. You don't edit this file.

One append-only log, three doors:

    GET  /events   -> SSE stream: full history, then live events
    POST /actions  -> {"type": "..."} delivered to a loop paused in wait_for()
    POST /run      -> start one episode (the loop in loop_runner.py)
    GET  /log      -> the whole log as JSON (what scripts/check.py reads)

Your assignment lives in loop_runner.py: three emit() calls. This server just
carries whatever the loop emits — that separation is the point.

Run it:   uv run uvicorn broadcast:app --port ${TABLE_PORT:-8323}
          (add RUNNER=solutions to use the finished loop instead of yours)
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

_HERE = os.path.dirname(os.path.abspath(__file__))
_FELT_OUT = os.path.join(_HERE, "..", "app", "out")          # `npm run build` output
_RUN_FILE = os.path.join(_HERE, "..", "app", "public", "run", "latest.json")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

LOG: list[dict] = []
SUBS: set[asyncio.Queue] = set()
ACTIONS: asyncio.Queue = asyncio.Queue()
RUNNING = False


def emit(type_: str, **payload) -> dict:
    """Append one event to the log and push it to every subscriber."""
    ev = {"i": len(LOG), "type": type_, **payload}
    LOG.append(ev)
    for q in list(SUBS):
        q.put_nowait(ev)
    return ev


async def wait_for(action_type: str) -> dict:
    """Pause the loop until a client POSTs {"type": action_type} to /actions."""
    emit("awaiting_action", action=action_type)
    while True:
        a = await ACTIONS.get()
        if a.get("type") == action_type:
            emit("action_received", action=action_type)
            return a


@app.get("/")
async def index():
    # Single-port mode: if the felt app has been built (`cd app && npm run
    # build`), this server IS the page — Cloud Shell Web Preview needs only
    # this one port. Without a build, leave a signpost instead of a 404.
    felt = os.path.join(_FELT_OUT, "index.html")
    if os.path.exists(felt):
        return FileResponse(felt, media_type="text/html")
    return {
        "this": "the Table for N event bus — an API, not a page",
        "open_instead": "http://localhost:3260 — the app; press Enter in its URL box to connect it here",
        "build_the_single_port_page": "cd app && npm install && npm run build — then reload this address",
        "doors": {
            "GET /events": "SSE: full history, then live",
            "POST /run": "start one episode",
            "POST /actions": "answer a paused loop",
            "GET /log": "the whole log as JSON",
        },
    }


@app.get("/run/latest.json")
async def latest_run():
    """The your-run file is written at runtime, after any static build."""
    if os.path.exists(_RUN_FILE):
        return FileResponse(_RUN_FILE, media_type="application/json",
                            headers={"Cache-Control": "no-store"})
    return JSONResponse({"detail": "no run yet"}, status_code=404)


@app.get("/events")
async def events():
    q: asyncio.Queue = asyncio.Queue()

    async def stream():
        for ev in list(LOG):
            yield f"data: {json.dumps(ev)}\n\n"
        SUBS.add(q)
        try:
            while True:
                ev = await q.get()
                yield f"data: {json.dumps(ev)}\n\n"
        finally:
            SUBS.discard(q)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@app.post("/actions")
async def actions(a: dict):
    await ACTIONS.put(a)
    return {"ok": True}


@app.post("/run")
async def run():
    global RUNNING
    if RUNNING:
        return {"ok": False, "error": "an episode is already running"}
    LOG.clear()
    runner = importlib.import_module(
        {"solutions": "solutions.loop_runner", "flywheel": "flywheel"}
        .get(os.environ.get("RUNNER", ""), "loop_runner"))
    RUNNING = True

    async def episode():
        global RUNNING
        try:
            await runner.run(emit, wait_for)
        except Exception as e:  # an error is an event too — the app shows it
            emit("error", message=f"{type(e).__name__}: {e}")
        finally:
            RUNNING = False

    asyncio.get_event_loop().create_task(episode())
    return {"ok": True}


@app.get("/log")
async def log():
    return {"events": LOG, "running": RUNNING}


if os.path.isdir(_FELT_OUT):
    app.mount("/", StaticFiles(directory=_FELT_OUT, html=True), name="felt")
