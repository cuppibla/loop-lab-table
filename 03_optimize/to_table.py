"""Put YOUR run on the table.  Usage: python to_table.py [p1]

The agent here reads `instruction_current.txt`. So this script answers one
question, live: what does the instruction that is on disk RIGHT NOW book?

Run it once as shipped (the day-one draft), swap the GEPA winner in, run it
again — same party, same model, same command. Only the instruction changed,
and the table changes with it.
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
INSTRUCTION = os.path.join(_LEVEL, "instruction_current.txt")


def write(events):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    stamp = time.time()
    with open(OUT, "w") as f:
        json.dump({"stamp": stamp, "events": events}, f, indent=1)
    _confirm(stamp, len(events))


def _confirm(stamp, n):
    """The table on :3260 must be THIS repo's app — say so plainly when it isn't."""
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(
                f"http://localhost:3260/run/latest.json?t={int(stamp)}", timeout=2) as r:
            served = json.load(r).get("stamp")
    except urllib.error.HTTPError:
        served = None          # an app answered, but it has no such file
    except Exception:
        print("\n⚠️  Wrote your run, but nothing is answering on http://localhost:3260.")
        print("   Start the app from THIS repo:   cd app && npm install && npm run dev")
        print("   then open http://localhost:3260 — your run plays on load.")
        return
    if served == stamp:
        print(f"\n📺 on the table → http://localhost:3260   ({n} events)")
    else:
        print("\n⚠️  The app on http://localhost:3260 is serving a DIFFERENT copy of this")
        print("   repo, so your runs will never appear on it. Stop that server, then")
        print("   from THIS repo:   cd app && npm run dev   — and rerun this script.")


def parse(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    d = json.loads(m.group(0)) if m else {}
    rid = world.find_restaurant(str(d.get("restaurant", "")))
    if rid is None:
        raise SystemExit(f"could not read a restaurant out of: {(text or '')[:120]!r}")
    t = re.search(r"(\d{1,2}:\d{2})", str(d.get("time", "")))
    return rid, (t.group(1) if t else "19:00"), str(d.get("reason", ""))[:220]


async def main(party):
    chars = len(open(INSTRUCTION).read())
    which = "the GEPA winner" if chars > 1200 else "the day-one draft"
    print(f"instruction_current.txt is {chars} characters — {which}")

    svc = InMemorySessionService()
    await svc.create_session(app_name="host", user_id="you", session_id="s1")
    runner = Runner(agent=root_agent, app_name="host", session_service=svc)
    out = ""
    async for ev in runner.run_async(user_id="you", session_id="s1",
            new_message=types.Content(role="user", parts=[types.Part(text=world.brief(party))])):
        if ev.is_final_response():
            out = ev.content.parts[0].text
    print(out)

    rid, when, why = parse(out)
    r = world.RESTAURANTS[rid]
    ids = world.PARTIES[party]
    score, seats = world.everyone_ate(ids, rid, when)

    events = [
        {"type": "episode_mode", "live": True, "engine": "your-run", "level": "03",
         "note": f"instruction_current.txt · {chars} chars · {which}"},
        {"type": "party_seated", "party_id": party, "people":
            [{"id": i, "name": world.PEOPLE[i]["name"], "label": world.PEOPLE[i]["label"]}
             for i in ids], "dt": 0.6},
        {"type": "pick_proposed", "restaurant": rid, "restaurant_name": r["name"],
         "rating": r["rating"], "time": when, "judge": "everyone_ate",
         "instruction": f"{which} · your live model call", "reason": why, "dt": 1.2},
    ]
    for s in seats:
        events.append({"type": "seat_scored", "person_id": s["id"], "name": s["name"],
                       "ate": s["ate"], "why": s["why"], "dt": 0.5})
    events.append({"type": "party_scored", "judge": "everyone_ate", "score": round(score, 2),
                   "ate": round(score * len(ids)), "total": len(ids),
                   "passed": score >= world.THRESHOLD, "threshold": world.THRESHOLD, "dt": 0.8})
    write(events)

    hungry = [s["name"] for s in seats if not s["ate"]]
    print(f"\n{len(ids) - len(hungry)}/{len(ids)} ate" +
          (f" — hungry: {', '.join(hungry)}" if hungry else " — the whole table"))


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "p1"))
