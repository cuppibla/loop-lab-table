"""Record the solutions episode into the app's replay file (no server needed).

    python scripts/record_replay.py

Writes ../app/public/replay/episode.json — a list of {dt, ...event}, where dt
is the pause before the event. awaiting_action events become the points where
the app's replay engine stops and waits for a real click on the judge switch.
"""
import asyncio
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
os.environ["TABLE_SPEED"] = "1"

from solutions import loop_runner  # noqa: E402

clock = 0.0
last = 0.0
events = []

_orig_sleep = asyncio.sleep


async def fake_sleep(d):
    global clock
    clock += d


def emit(type_, **payload):
    global last
    events.append({"dt": round(clock - last, 2), "type": type_, **payload})
    last = clock
    return events[-1]


async def wait_for(action):
    emit("awaiting_action", action=action)
    emit("action_received", action=action)


async def main():
    asyncio.sleep = fake_sleep
    try:
        await loop_runner.run(emit, wait_for)
    finally:
        asyncio.sleep = _orig_sleep


asyncio.run(main())

out = os.path.join(os.path.dirname(HERE), "app", "public", "replay", "episode.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w") as f:
    json.dump(events, f, indent=1)
print(f"wrote {out}  ({len(events)} events, {clock:.0f}s of story)")
