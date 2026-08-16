"""Phase-0 oracle: run the CURRENT host instruction on every party and grade it.

Usage:  .venv/bin/python scripts/naive_baseline.py [01_host]
        (argument = which level's host/ + world.py to use; default 01_host)

Prints a per-party table (honest + rating judges) and the holdout summary the
codelab quotes as the baseline.
"""
import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEVEL = sys.argv[1] if len(sys.argv) > 1 else "01_host"
sys.path.insert(0, os.path.join(ROOT, LEVEL))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))
if os.environ.get("GOOGLE_API_KEY"):
    # an AI Studio key wins locally; without one, Vertex mode is respected
    os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)

from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

import world  # noqa: E402
from host import root_agent  # noqa: E402

from metricsless_parse import parse_decision  # noqa: E402  (see below)


async def ask(runner, svc, pid: str) -> str:
    sid = f"s-{pid}"
    await svc.create_session(app_name="host", user_id="lab", session_id=sid)
    out = ""
    async for ev in runner.run_async(
        user_id="lab", session_id=sid,
        new_message=types.Content(role="user", parts=[types.Part(text=world.brief(pid))]),
    ):
        if ev.is_final_response():
            out = ev.content.parts[0].text or ""
    return out


async def main():
    svc = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name="host", session_service=svc)

    rows = []
    for pid in list(world.TRAIN) + list(world.HOLDOUT):
        raw = await ask(runner, svc, pid)
        rid, time_str = parse_decision(raw)
        if rid is None:
            rows.append((pid, "?", "?", 0.0, 0.0, ["unparseable decision"]))
            continue
        honest, seats = world.everyone_ate(world.PARTIES[pid], rid, time_str)
        gameable, _ = world.rating_score(world.PARTIES[pid], rid, time_str)
        whys = [f"{s['name']}: {s['why']}" for s in seats if not s["ate"]]
        rows.append((pid, world.RESTAURANTS[rid]["name"], time_str, honest, gameable, whys))

    print(f"{'party':<6}{'pick':<18}{'time':<8}{'honest':<9}{'rating':<9}split")
    hold_pass = hold_n = 0
    hold_scores, hungry, seats_total = [], 0, 0
    for pid, name, t, honest, gameable, whys in rows:
        split = "holdout" if pid in world.HOLDOUT else "train"
        verdict = "PASS" if honest >= world.THRESHOLD else "FAIL"
        if split == "holdout":
            hold_n += 1
            hold_pass += verdict == "PASS"
            hold_scores.append(honest)
            n = len(world.PARTIES[pid])
            seats_total += n
            hungry += round((1 - honest) * n)
        print(f"{pid:<6}{name:<18}{t:<8}{honest:<9.2f}{gameable:<9.2f}{split}  {verdict}")
        for w in whys:
            print(f"{'':>14}- {w}")
    mean = sum(hold_scores) / len(hold_scores) if hold_scores else 0.0
    print(f"\nHOLDOUT: {hold_pass}/{hold_n} passed (bar {world.THRESHOLD}) | "
          f"mean score {mean:.2f} | {hungry} of {seats_total} seats left hungry")


if __name__ == "__main__":
    asyncio.run(main())
