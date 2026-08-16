"""SOLUTIONS — the flywheel with YOUR EDGE written in. Try flywheel.py first.

    host (agent — its instruction is TEMPLATED FROM STATE)
      -> judge (the level-02 pure function; whys go into state)
      -> router (the BOUNDARY lives here — see below)
      -> proposer (an LLM node that rewrites the instruction from the whys)
      -> publish -> back to host

Every round, the proposer's rewrite lands in `state.current_instruction`,
and the next host call runs UNDER THE NEW INSTRUCTION. The loop is the
level-03 flywheel with the 20-minute optimizer swapped for a one-breath
proposer — small enough to run live, honest enough to keep the three roles
separated: the host never grades, the judge never proposes, the router
never writes.

**ADK 2 does the loop natively** (a route edge pointing back — the
08_loop_self pattern). What it does NOT give you is a boundary: nothing in
`Workflow` caps iterations. The router owns it, with three belts:

  1. SHIP the moment the judge passes (score >= world.THRESHOLD);
  2. STOP at FLY_MAX_ROUNDS (default 4 — that's <= 8 model calls);
  3. STOP EARLY after 2 rounds with no improvement (a flat line is an
     answer too — spend no more money on it).

Run it standalone (needs GOOGLE_API_KEY):

    uv run python flywheel.py

or serve it to the app (the climb bars grow live, round by round):

    RUNNER=flywheel uv run uvicorn broadcast:app --port 8323
"""
from __future__ import annotations

import asyncio
import difflib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import world  # noqa: E402
from loop_runner import (SPEED, parse_decision, _pick_payload, _party_scored,  # noqa: E402
                         _people, PARTY)


def _nap(seconds: float):
    if SPEED > 0:
        time.sleep(min(seconds * SPEED, 0.5))

MAX_ROUNDS = int(os.environ.get("FLY_MAX_ROUNDS", "4"))
MAX_INSTRUCTION_CHARS = 2400  # a runaway proposer gets truncated, not obeyed

_HERE = os.path.dirname(os.path.abspath(__file__))
DRAFT = open(os.path.join(_HERE, "instruction_draft.txt")).read()

PROPOSER_INSTRUCTION = """You are the coach in a self-improving loop. An agent books dinner tables; \
a deterministic judge just scored its latest booking. Your ONLY job is to rewrite the agent's \
instruction so the next booking feeds everyone.

The judge's failure notes for the latest booking:
{whys}

The agent's current instruction:
---
{current_instruction}
---

Write ONLY the replacement instruction (plain text, no commentary, under 1200 characters). \
Turn each failure note into a concrete rule. Keep the JSON output-format section verbatim."""


async def run(emit, wait_for):
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_HERE, "..", ".env"))
    os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)
    from google.adk import Agent, Event, Workflow
    from google.adk.runners import InMemoryRunner
    from google.genai import types as gt

    ids = world.PARTIES[PARTY]
    n = len(ids)
    ep: dict = {"round": 0, "best": 0.0, "flat": 0, "baseline": None, "done": False}

    gen = gt.GenerateContentConfig(
        thinking_config=gt.ThinkingConfig(thinking_budget=0), temperature=0.0)

    def seed(node_input: str):
        emit("episode_mode", live=True, engine="adk-workflow-flywheel")
        emit("party_seated", party_id=PARTY, people=_people())
        yield Event(state={"brief": world.brief(PARTY),
                           "current_instruction": DRAFT,
                           "whys": "(no failures yet — first round)"})

    host = Agent(
        name="host", model="gemini-2.5-flash",
        # the whole point: the instruction is a STATE TEMPLATE — the loop
        # rewrites it while the graph is running
        instruction="{current_instruction}\n\nHere is tonight's request:\n{brief}",
        output_key="decision", generate_content_config=gen)

    def judge(decision: str):
        ep["round"] += 1
        rid, t, reason = parse_decision(decision)
        emit("pick_proposed", **_pick_payload(rid, t, judge="everyone_ate",
             instruction=f"flywheel round {ep['round']} · live model call", reason=reason))
        _nap(2.0)
        score, seats = world.everyone_ate(ids, rid, t)
        for s in seats:
            emit("seat_scored", person_id=s["id"], name=s["name"], ate=s["ate"], why=s["why"])
            _nap(0.5)
        _party_scored(emit, "everyone_ate", score, n, world.THRESHOLD)
        if ep["baseline"] is None:
            ep["baseline"] = score
        emit("holdout_scored", round=ep["round"], score=round(score, 2),
             baseline=round(ep["baseline"], 2))
        _nap(2.0)
        whys = "; ".join(f"{s['name']}: {s['why']}" for s in seats if not s["ate"]) or "none"
        yield Event(state={"whys": whys, "last_score": score})

    def router(last_score: float):
        # ── THE BOUNDARY. ADK gives you the loop; nobody but you gives it an end.
        if last_score >= world.THRESHOLD:
            emit("gate_decided", decision="SHIP", judge="everyone_ate",
                 score=round(last_score, 2), baseline=round(ep["baseline"], 2),
                 why=f"passed in round {ep['round']} — the loop earned its exit")
            yield Event(route="ship")
        elif ep["round"] >= MAX_ROUNDS:
            emit("gate_decided", decision="REJECT", judge="everyone_ate",
                 score=round(last_score, 2), baseline=round(ep["baseline"], 2),
                 why=f"round budget exhausted ({MAX_ROUNDS}) — stopping is also a decision")
            yield Event(route="ship")
        elif last_score <= ep["best"] and ep["flat"] >= 1:
            emit("gate_decided", decision="REJECT", judge="everyone_ate",
                 score=round(last_score, 2), baseline=round(ep["baseline"], 2),
                 why="two rounds without improvement — a flat line is an answer too")
            yield Event(route="ship")
        else:
            ep["flat"] = ep["flat"] + 1 if last_score <= ep["best"] else 0
            ep["best"] = max(ep["best"], last_score)
            yield Event(route="improve")

    proposer = Agent(
        name="proposer", model="gemini-2.5-flash",
        instruction=PROPOSER_INSTRUCTION,
        output_key="proposed_instruction", generate_content_config=gen)

    def publish(proposed_instruction: str, current_instruction: str):
        new = proposed_instruction.strip()[:MAX_INSTRUCTION_CHARS]  # belt #4
        if os.environ.get("FLY_DEBUG"):
            print(f"\n----- the rewrite, verbatim (round {ep['round']}) -----\n{new}\n-----")
        diff = [{"op": l[0], "line": l[1:].strip()[:110]}
                for l in difflib.unified_diff(
                    current_instruction.splitlines(), new.splitlines(), lineterm="")
                if l[:1] in "+-" and not l.startswith(("+++", "---")) and l[1:].strip()][:8]
        emit("candidate_proposed", candidate_id=f"R-{ep['round']}",
             diff=diff or [{"op": "+", "line": "(rewrite too large to diff — full text swapped)"}],
             proposer="flywheel proposer (LLM node)")
        yield Event(state={"current_instruction": new})

    def done(node_input=None):
        emit("episode_done")
        ep["done"] = True
        yield Event(message=f"flywheel closed after round {ep['round']}")

    fly = Workflow(
        name="flywheel",
        edges=[
            ("START", seed, host, judge, router),
            (router, {"improve": proposer, "ship": done}),
            (proposer, publish, host),   # <- the route back: the loop itself
        ],
    )

    runner = InMemoryRunner(agent=fly, app_name="flywheel")
    session = await runner.session_service.create_session(app_name="flywheel", user_id="app")
    async for _ev in runner.run_async(
            user_id="app", session_id=session.id,
            new_message=gt.Content(role="user", parts=[gt.Part(text="spin")])):
        pass
    if not ep["done"]:
        emit("error", message="flywheel ended without closing — check the log")


if __name__ == "__main__":
    def _print_emit(type_, **payload):
        line = {k: v for k, v in payload.items() if k not in ("people", "diff")}
        print(f"[{type_}] {line}")

    async def _no_wait(_):
        return {}

    asyncio.run(run(_print_emit, _no_wait))
