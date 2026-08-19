"""Run YOUR agent on one party and score it.  Usage: python to_table.py [p1]

Same live model call as level 01 — but now the booking gets judged, and the
verdict stamp comes from YOUR code:

    seats      <- world.everyone_ate  (walks the table, seat by seat)
    the stamp  <- metrics/table.py::_status  (the same file adk eval imports)
"""
import asyncio
import json
import os
import re
import sys
import time

from dotenv import load_dotenv

_LEVEL = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _LEVEL)
load_dotenv(os.path.join(_LEVEL, "..", ".env"))
if os.environ.get("GOOGLE_API_KEY"):
    # an AI Studio key wins locally; without one, Vertex mode is respected
    os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)

from google.adk.evaluation.eval_metrics import EvalStatus  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

import world  # noqa: E402
from host import root_agent  # noqa: E402
from metrics.table import _status  # noqa: E402  <- YOUR code decides the stamp



def write(events):
    """No-op: the felt table UI was removed. Results print to stdout."""
    return



def parse(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    d = json.loads(m.group(0)) if m else {}
    rid = world.find_restaurant(str(d.get("restaurant", "")))
    if rid is None:
        raise SystemExit(f"could not read a restaurant out of: {(text or '')[:120]!r}")
    t = re.search(r"(\d{1,2}:\d{2})", str(d.get("time", "")))
    return rid, (t.group(1) if t else "19:00"), str(d.get("reason", ""))[:220]


async def main(party):
    svc = InMemorySessionService()
    await svc.create_session(app_name="host", user_id="you", session_id="s1")
    runner = Runner(agent=root_agent, app_name="host", session_service=svc)
    print(f"asking your agent to book {party}…")
    out = ""
    async for ev in runner.run_async(user_id="you", session_id="s1",
            new_message=types.Content(role="user", parts=[types.Part(text=world.brief(party))])):
        if ev.is_final_response() and ev.content and ev.content.parts:
            out = ev.content.parts[0].text
    if not out:
        sys.exit("\n✗ No answer from the model.\n  If you saw 429 RESOURCE_EXHAUSTED above, the region is out of shared\n  quota. Set GOOGLE_CLOUD_LOCATION=global in ~/loop-lab-table/.env and\n  re-run. Nothing in your code is broken.")
    print(out)

    rid, when, why = parse(out)
    r = world.RESTAURANTS[rid]
    ids = world.PARTIES[party]
    score, seats = world.everyone_ate(ids, rid, when)
    passed = _status(score, world.THRESHOLD) == EvalStatus.PASSED  # <- YOUR two lines

    events = [
        {"type": "episode_mode", "live": True, "engine": "your-run", "level": "02",
         "note": "seats: world.everyone_ate · the PASSED/FAILED stamp: your metrics/table.py"},
        {"type": "party_seated", "party_id": party, "people":
            [{"id": i, "name": world.PEOPLE[i]["name"], "label": world.PEOPLE[i]["label"]}
             for i in ids], "dt": 0.6},
        {"type": "pick_proposed", "restaurant": rid, "restaurant_name": r["name"],
         "rating": r["rating"], "time": when, "judge": "everyone_ate",
         "instruction": "day-one draft · your live model call", "reason": why, "dt": 1.2},
    ]
    for s in seats:
        events.append({"type": "seat_scored", "person_id": s["id"], "name": s["name"],
                       "ate": s["ate"], "why": s["why"], "dt": 0.5})
    events.append({"type": "party_scored", "judge": "everyone_ate", "score": round(score, 2),
                   "ate": round(score * len(ids)), "total": len(ids), "passed": passed,
                   "threshold": world.THRESHOLD, "dt": 0.8})
    write(events)

    hungry = [s["name"] for s in seats if not s["ate"]]
    print(f"\nseats: {len(ids) - len(hungry)}/{len(ids)} ate" +
          (f" — hungry: {', '.join(hungry)}" if hungry else ""))
    print(f"your metric stamped: {'PASSED' if passed else 'FAILED'}"
          + ("   <- with people still hungry. That is the bug." if hungry and passed else ""))


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "p1"))
