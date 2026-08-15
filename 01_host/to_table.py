"""Put YOUR run on the table.  Usage: python to_table.py [p1]

Runs the agent in host/agent.py against a real party brief — one real model
call — and writes what happened to the app as an event file. The table at
http://localhost:3260 picks it up within a second or two.

Level 01 emits exactly two things: the party, and the agent's pick. No seats
light up, no score appears, because nothing in this system can judge yet.
That empty verdict IS level 01.
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
os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)

from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

import world  # noqa: E402
from host import root_agent  # noqa: E402

OUT = os.path.join(_LEVEL, "..", "app", "public", "run", "latest.json")


def write(events):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump({"stamp": time.time(), "events": events}, f, indent=1)
    print(f"\n📺 on the table → http://localhost:3260   ({len(events)} events)")


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
        if ev.is_final_response():
            out = ev.content.parts[0].text
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
