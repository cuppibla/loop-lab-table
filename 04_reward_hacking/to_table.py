"""Put YOUR run on the table.  Usage: python to_table.py [p1]

The agent here reads `instruction_start.txt`. Swap the gameable winner in and
run this again: the table shows both judges at once — the seats are still
scored honestly (people go grey), while the verdict on screen is the RATING,
which is delighted.

That split screen is the whole level.
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

OUT = os.path.join(_LEVEL, "..", "app", "public", "run", "latest.json")
INSTRUCTION = os.path.join(_LEVEL, "instruction_start.txt")


def write(events):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    stamp = time.time()
    with open(OUT, "w") as f:
        json.dump({"stamp": stamp, "events": events}, f, indent=1)
    _confirm(stamp, len(events))


def _confirm(stamp, n):
    """Find the table that will actually play this run, and say so plainly."""
    import urllib.error
    import urllib.request
    ports = [3260, 8323]                      # next dev · the bus (single-port)
    if os.environ.get("TABLE_APP_PORT"):
        ports.insert(0, int(os.environ["TABLE_APP_PORT"]))
    answered = []
    for port in ports:
        try:
            with urllib.request.urlopen(
                    f"http://localhost:{port}/run/latest.json?t={int(stamp)}",
                    timeout=2) as r:
                if json.load(r).get("stamp") == stamp:
                    print(f"\n📺 on the table → http://localhost:{port}   ({n} events)")
                    return
                answered.append(port)
        except urllib.error.HTTPError:
            answered.append(port)             # an app, but a different copy / no file
        except Exception:
            pass                              # nothing on this port
    if answered:
        print(f"\n⚠️  An app answered on port {answered[0]} but it is serving a DIFFERENT")
        print("   copy of this repo — your runs will never appear there. Stop it, then")
        print("   from THIS repo:  cd app && npm run dev  (or serve the bus with the")
        print("   felt built: cd app && npm run build, then run the broadcast server).")
    else:
        print("\n⚠️  Wrote your run, but no app is answering (tried "
              + ", ".join(str(p) for p in ports) + ").")
        print("   Start one from THIS repo:  cd app && npm install && npm run dev")
        print("   then open http://localhost:3260 — your run plays on load.")


def parse(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    d = json.loads(m.group(0)) if m else {}
    rid = world.find_restaurant(str(d.get("restaurant", "")))
    if rid is None:
        raise SystemExit(f"could not read a restaurant out of: {(text or '')[:120]!r}")
    t = re.search(r"(\d{1,2}:\d{2})", str(d.get("time", "")))
    return rid, (t.group(1) if t else "19:00"), str(d.get("reason", ""))[:220]


async def main(party):
    text = open(INSTRUCTION).read()
    hacked = "rating" in text.lower() and "highest-rated" in text.lower()
    which = "the gameable winner" if hacked else "the day-one draft"
    print(f"instruction_start.txt is {len(text)} characters — {which}")

    svc = InMemorySessionService()
    await svc.create_session(app_name="host", user_id="you", session_id="s1")
    runner = Runner(agent=root_agent, app_name="host", session_service=svc)
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
    honest, seats = world.everyone_ate(ids, rid, when)
    rating, _ = world.rating_score(ids, rid, when)

    events = [
        {"type": "episode_mode", "live": True, "engine": "your-run", "level": "04",
         "note": f"instruction_start.txt · {which} · both judges, same booking"},
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
    events += [
        {"type": "party_scored", "judge": "everyone_ate", "score": round(honest, 2),
         "ate": round(honest * len(ids)), "total": len(ids),
         "passed": honest >= world.THRESHOLD, "threshold": world.THRESHOLD, "dt": 1.0},
        {"type": "judge_switched", "from": "everyone_ate", "to": "rating", "dt": 1.4},
        {"type": "party_scored", "judge": "rating", "score": round(rating, 2),
         "ate": round(honest * len(ids)), "total": len(ids),
         "passed": rating >= world.RATING_BAR, "threshold": world.RATING_BAR, "dt": 0.8},
    ]
    write(events)

    hungry = [s["name"] for s in seats if not s["ate"]]
    print(f"\nhonest judge: {honest:.2f}" + (f" — hungry: {', '.join(hungry)}" if hungry else ""))
    print(f"rating judge: {rating:.2f}"
          + ("   <- the same booking, and this judge is delighted." if hungry else ""))


asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "p1"))
