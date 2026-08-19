"""Run YOUR agent on one party and print what it booked.  Usage: python to_table.py [p1]

Runs the agent in host/agent.py against a real party brief — one real model
call.

Level 01 prints exactly two things: the party, and the agent's pick. No score
appears, because nothing in this system can judge yet. That empty verdict IS
level 01.
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

from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

import world  # noqa: E402
from host import root_agent  # noqa: E402



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
    people = [{"id": i, "name": world.PEOPLE[i]["name"], "label": world.PEOPLE[i]["label"]}
              for i in world.PARTIES[party]]
    write([
        {"type": "episode_mode", "live": True, "engine": "your-run", "level": "01",
         "note": "your agent booked this — and nothing in the system can say whether it is good"},
        {"type": "party_seated", "party_id": party, "people": people, "dt": 0.6},
        {"type": "pick_proposed", "restaurant": rid, "restaurant_name": r["name"],
         "rating": r["rating"], "time": when, "judge": "everyone_ate",
         "instruction": "day-one draft · your live model call", "reason": why, "dt": 1.2},
    ])
    print("The seats stay neutral on purpose: level 01 has no judge.")


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "p1"))
