"""SOLUTIONS — the three emit() calls, filled. Try loop_runner.py yourself first.

The episode has TWO engines, one contract:

  * **scripted** (default) — a hand-written async spine playing the measured
    numbers from levels 01-04. No key needed; this is what scripts/check.py
    grades and what the replay recording is made from.
  * **ADK 2 Workflow** (`TABLE_LIVE=1`) — the same spine as a real
    `Workflow(edges=[...])`: the three instructions run as AGENT NODES (every
    pick is a live model call), the judge and coach are function nodes, and
    the judge switch is a **`RequestInput`** — ADK's human-in-the-loop pause.
    The workflow halts there until the app's switch is pressed.

Both engines call the same three functions below. Fill the emits marked

        # ── YOUR EMIT #n ──────────────────────────────────────────

run `python scripts/check.py`, and the table lights up with YOUR events —
under either engine. solutions/loop_runner.py has the answers — try first.
"""
from __future__ import annotations

import asyncio
import json as _json
import os
import re as _re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import world  # noqa: E402

SPEED = float(os.environ.get("TABLE_SPEED", "1"))  # 0 = no pacing (check.py)
LIVE = os.environ.get("TABLE_LIVE", "") == "1"  # 1 = the ADK 2 Workflow engine
_HERE = os.path.dirname(os.path.abspath(__file__))
_BASE = os.path.dirname(_HERE)  # where the three instruction artifacts live

PARTY = "p1"  # Nadia · Tom · Amara · Lena · Ben — the draft's worst night
# The three instructions ARE the lab's artifacts: the day-one draft (01), the
# GEPA winner (03, prebaked from a real run), the ratings hack (04). The
# tuples carry the measured fallback picks for the scripted engine.
DRAFT_PICK = ("instruction_draft.txt", "olive", "19:00",
              "Olive & Thyme fits the vibe — shareable, quiet, something for everyone.")
WINNER_PICK = ("instruction_winner.txt", "pho", "19:45",
               "Pho Saigon at 7:45 — vegan pho for Nadia, $18 under Tom's cap, "
               "4-min walk for Amara, kitchen serves until 9:30 for Lena.")
HACKED_PICK = ("instruction_hacked.txt", "smoke", "19:30",
               "Smoke & Barrel — ★4.9, the hottest room in the district.")

# The real climb from prebaked/gepa_run_log.txt (valset aggregate):
CLIMB = [(0, 0.375), (1, 0.375), (3, 0.75)]
BASELINE = 0.375

# The load-bearing lines of the real diff (03_optimize/prebaked/):
DIFF = [
    {"op": "-", "line": "lead with the highest-rated, most talked-about room that fits the night"},
    {"op": "+", "line": "Understand Group Requirements: carefully parse the chat for each individual's needs"},
    {"op": "+", "line": "Filter restaurants by absolute constraints — a single violation for one person eliminates the room for the whole group"},
    {"op": "+", "line": "Budget: strictly adhere to any 'under $X a head' limits"},
    {"op": "+", "line": "Last orders: ensure the booking allows everyone — including late arrivals — to order before the cutoff"},
    {"op": "+", "line": "Only among the survivors, prefer the higher-rated room"},
]

# The REAL production night (level 06, run 2026-08-14): 13 conversations against
# the deployed engine, 7/8 dinners fed everyone. The one failure and the one
# hallucination below are verbatim from the harvest.
AFTERMATH = [
    {"party": "p2", "person_id": "lena", "predicted": True, "actual": False,
     "why": "Taqueria Luna — she said 7:45, the counter's last orders are 7:30. "
            "The night's only failure, on the exact seat the exam ceiling predicted."},
]
FANTOME = ("chez-fantome — the agent BOOKED a restaurant that does not exist; "
           "the pure function [skip]ped it. Invented restaurants are the platform judge's job")


# ════════════════════════════════════════════════════════════════════
# YOUR THREE EMITS — shared by both engines
# ════════════════════════════════════════════════════════════════════

def emit_seat(emit, s):
    """One seat's verdict. The app greys a chair the moment this arrives."""
    emit("seat_scored", person_id=s["id"], name=s["name"], ate=s["ate"], why=s["why"])


def propose_candidate(emit):
    """The coach's proposal. The diff card is the star of act three."""
    emit("candidate_proposed", candidate_id="C-1", diff=DIFF, proposer="gepa")


def decide_gate(emit, decision, judge, score, baseline, why):
    """The verdict. SHIP stamps green; REJECT stamps red."""
    emit("gate_decided", decision=decision, judge=judge, score=score,
         baseline=baseline, why=why)


# ════════════════════════════════════════════════════════════════════
# shared helpers
# ════════════════════════════════════════════════════════════════════

def parse_decision(text: str):
    """Model text -> (restaurant_id, 'HH:MM', reason). Raises if unparseable."""
    m = _re.search(r"\{.*\}", text or "", _re.S)
    d = _json.loads(m.group(0)) if m else {}
    rid = world.find_restaurant(str(d.get("restaurant", "")))
    if rid is None:
        raise ValueError(f"unparseable decision: {(text or '')[:80]!r}")
    t = _re.search(r"(\d{1,2}:\d{2})", str(d.get("time", "")))
    return rid, (t.group(1) if t else "19:00"), str(d.get("reason", ""))[:220]


def _pick_payload(rid, time_str, judge, instruction, reason):
    r = world.RESTAURANTS[rid]
    return dict(restaurant=rid, restaurant_name=r["name"], rating=r["rating"],
                time=time_str, judge=judge, instruction=instruction, reason=reason)


def _party_scored(emit, judge, score, n, bar):
    emit("party_scored", judge=judge, score=round(score, 2),
         ate=round(score * n), total=n, passed=score >= bar, threshold=bar)


def _people():
    return [{"id": i, "name": world.PEOPLE[i]["name"], "label": world.PEOPLE[i]["label"]}
            for i in world.PARTIES[PARTY]]


def _aftermath(emit):
    for o in AFTERMATH:
        emit("outcome_returned", **o, name=world.PEOPLE[o["person_id"]]["name"])
        emit("exam_minted", case_id=f"harvested-{o['party']}-{o['person_id']}",
             from_outcome=o["why"])
    emit("exam_minted", case_id=FANTOME,
         from_outcome="caught by the platform judge, not the metric")
    emit("episode_done")


async def pace(seconds: float):
    if SPEED > 0:
        await asyncio.sleep(seconds * SPEED)


# ════════════════════════════════════════════════════════════════════
# engine 1 · the scripted spine (default; what check.py grades)
# ════════════════════════════════════════════════════════════════════

async def score_table(emit, party_ids, rid, time_str):
    """Walk the table, one seat at a time."""
    score, seats = world.everyone_ate(party_ids, rid, time_str)
    for s in seats:
        emit_seat(emit, s)
        await pace(0.6)
    return score


async def run_scripted(emit, wait_for):
    ids = world.PARTIES[PARTY]
    emit("episode_mode", live=False, engine="scripted")
    emit("party_seated", party_id=PARTY, people=_people())
    await pace(2.0)

    _, d_rid, d_time, d_reason = DRAFT_PICK
    emit("pick_proposed", **_pick_payload(d_rid, d_time, judge="everyone_ate",
                                          instruction="day-one draft", reason=d_reason))
    await pace(2.5)
    score = await score_table(emit, ids, d_rid, d_time)
    _party_scored(emit, "everyone_ate", score, len(ids), world.THRESHOLD)
    await pace(2.5)

    propose_candidate(emit)
    await pace(2.0)
    for rnd, s in CLIMB:
        emit("holdout_scored", round=rnd, score=s, baseline=BASELINE)
        await pace(1.2)
    decide_gate(emit, "SHIP", "everyone_ate", 0.75, BASELINE,
                "6/8 on parties it never saw · 2 of 36 seats hungry (was 6)")
    await pace(2.0)

    _, w_rid, w_time, w_reason = WINNER_PICK
    emit("pick_proposed", **_pick_payload(w_rid, w_time, judge="everyone_ate",
                                          instruction="GEPA winner", reason=w_reason))
    score = await score_table(emit, ids, w_rid, w_time)
    _party_scored(emit, "everyone_ate", score, len(ids), world.THRESHOLD)
    await pace(1.5)

    await wait_for("switch_judge")
    emit("judge_switched", **{"from": "everyone_ate", "to": "rating"})
    await pace(1.5)
    _, h_rid, h_time, h_reason = HACKED_PICK
    emit("pick_proposed", **_pick_payload(h_rid, h_time, judge="rating",
                                          instruction="what the ratings judge wants",
                                          reason=h_reason))
    score = await score_table(emit, ids, h_rid, h_time)
    rscore, _ = world.rating_score(ids, h_rid, h_time)
    _party_scored(emit, "rating", rscore, len(ids), world.RATING_BAR)
    await pace(2.0)

    await wait_for("switch_judge")
    emit("judge_switched", **{"from": "rating", "to": "everyone_ate"})
    await pace(1.0)
    _party_scored(emit, "everyone_ate", score, len(ids), world.THRESHOLD)
    decide_gate(emit, "REJECT", "everyone_ate", round(score, 2), 0.75,
                "same candidate, honest judge: the rating doubled, the table did not move")
    await pace(2.5)
    _aftermath(emit)


# ════════════════════════════════════════════════════════════════════
# engine 2 · the ADK 2 Workflow (TABLE_LIVE=1; every pick a real call)
#
# The spine as a graph. Agent nodes run the three instruction artifacts
# against the party brief (state-templated via {brief}); function nodes
# judge, coach, and gate; RequestInput halts the graph at the human switch
# until the app's button POSTs the action.
# ════════════════════════════════════════════════════════════════════

async def run_workflow(emit, wait_for):
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_BASE, "..", ".env"))
    os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)
    from google.adk import Agent, Event, Workflow
    from google.adk.events import RequestInput
    from google.adk.runners import InMemoryRunner
    from google.genai import types as gt

    ids = world.PARTIES[PARTY]
    n = len(ids)
    ep: dict = {}  # cross-node scratch (plain closure — no state templating needed)

    def _nap(seconds: float):
        if SPEED > 0:
            time.sleep(min(seconds * SPEED, 0.4))

    def _host(name, instruction_file, output_key):
        """An instruction artifact as a workflow AGENT NODE — a real model call."""
        return Agent(
            name=name, model="gemini-2.5-flash",
            instruction=open(os.path.join(_BASE, instruction_file)).read()
            + "\n\nHere is tonight's request:\n{brief}",
            output_key=output_key,
            generate_content_config=gt.GenerateContentConfig(
                thinking_config=gt.ThinkingConfig(thinking_budget=0), temperature=0.0))

    def seat_party(node_input: str):
        emit("episode_mode", live=True, engine="adk-workflow")
        emit("party_seated", party_id=PARTY, people=_people())
        yield Event(state={"brief": world.brief(PARTY)})

    draft_host = _host("draft_host", "instruction_draft.txt", "draft_decision")

    def judge_draft(draft_decision: str):
        rid, t, reason = parse_decision(draft_decision)
        emit("pick_proposed", **_pick_payload(rid, t, judge="everyone_ate",
             instruction="day-one draft · live model call", reason=reason))
        score, seats = world.everyone_ate(ids, rid, t)
        for s in seats:
            emit_seat(emit, s)
            _nap(0.3)
        _party_scored(emit, "everyone_ate", score, n, world.THRESHOLD)
        yield Event(message=f"draft scored {score:.2f}")

    def coach(node_input=None):
        propose_candidate(emit)
        _nap(0.4)
        for rnd, s in CLIMB:
            emit("holdout_scored", round=rnd, score=s, baseline=BASELINE)
            _nap(0.3)
        decide_gate(emit, "SHIP", "everyone_ate", 0.75, BASELINE,
                    "6/8 on parties it never saw · 2 of 36 seats hungry (was 6)")
        yield Event(message="candidate shipped")

    winner_host = _host("winner_host", "instruction_winner.txt", "winner_decision")

    def judge_winner(winner_decision: str):
        rid, t, reason = parse_decision(winner_decision)
        emit("pick_proposed", **_pick_payload(rid, t, judge="everyone_ate",
             instruction="GEPA winner · live model call", reason=reason))
        score, seats = world.everyone_ate(ids, rid, t)
        for s in seats:
            emit_seat(emit, s)
            _nap(0.3)
        _party_scored(emit, "everyone_ate", score, n, world.THRESHOLD)
        yield Event(message=f"winner scored {score:.2f}")

    def ask_switch(node_input=None):
        # ADK's human-in-the-loop: the graph HALTS here until input arrives.
        yield RequestInput(message="The loop is paused. Flip the judge to `rating` to continue.")

    def on_switch(node_input: str):
        emit("judge_switched", **{"from": "everyone_ate", "to": "rating"})
        yield Event(message="graded on ratings now")

    hacked_host = _host("hacked_host", "instruction_hacked.txt", "hacked_decision")

    def judge_hacked(hacked_decision: str):
        rid, t, reason = parse_decision(hacked_decision)
        emit("pick_proposed", **_pick_payload(rid, t, judge="rating",
             instruction="what the ratings judge wants · live model call", reason=reason))
        score, seats = world.everyone_ate(ids, rid, t)
        for s in seats:
            emit_seat(emit, s)
            _nap(0.3)
        rscore, _ = world.rating_score(ids, rid, t)
        _party_scored(emit, "rating", rscore, n, world.RATING_BAR)
        ep["hacked_honest"] = score
        yield Event(message=f"rating judge says {rscore:.2f}")

    def ask_switch_back(node_input=None):
        yield RequestInput(message="Flip the judge back — re-test the same candidate honestly.")

    def on_switch_back(node_input: str):
        emit("judge_switched", **{"from": "rating", "to": "everyone_ate"})
        score = ep.get("hacked_honest", 0.0)
        _party_scored(emit, "everyone_ate", score, n, world.THRESHOLD)
        decide_gate(emit, "REJECT", "everyone_ate", round(score, 2), 0.75,
                    "same candidate, honest judge: the rating doubled, the table did not move")
        yield Event(message="rejected at the gate")

    # ── THE ENCORE (the level-05 workflow exercise, solved) ────────
    # After the REJECT: seat p2 — the party production will fail on in
    # level 06 — and run the WINNER instruction on it, live.
    def encore_setup(node_input=None):
        p2 = [{"id": i, "name": world.PEOPLE[i]["name"], "label": world.PEOPLE[i]["label"]}
              for i in world.PARTIES["p2"]]
        emit("party_seated", party_id="p2", people=p2)
        yield Event(state={"brief": world.brief("p2")})

    encore_host = _host("encore_host", "instruction_winner.txt", "encore_decision")

    def judge_encore(encore_decision: str):
        rid, t, reason = parse_decision(encore_decision)
        emit("pick_proposed", **_pick_payload(rid, t, judge="everyone_ate",
             instruction="the encore · GEPA winner on p2 · live model call", reason=reason))
        p2 = world.PARTIES["p2"]
        score, seats = world.everyone_ate(p2, rid, t)
        for s in seats:
            emit_seat(emit, s)
            _nap(0.3)
        _party_scored(emit, "everyone_ate", score, len(p2), world.THRESHOLD)
        yield Event(message=f"encore scored {score:.2f}")

    def aftermath(node_input=None):
        _aftermath(emit)
        ep["done"] = True
        yield Event(message="episode over")

    episode = Workflow(
        name="episode",
        edges=[(
            "START", seat_party,
            draft_host, judge_draft,
            coach,
            winner_host, judge_winner,
            ask_switch, on_switch,
            hacked_host, judge_hacked,
            ask_switch_back, on_switch_back,
            encore_setup, encore_host, judge_encore,
            aftermath,
        )],
    )

    # Driving a halted graph is the same contract as any long-running tool:
    # the RequestInput surfaces as a function call whose id sits in
    # ev.long_running_tool_ids, and the resume is a function_response aimed
    # at that exact id. (The recipe from the long-running lab, verbatim.)
    runner = InMemoryRunner(agent=episode, app_name="episode")
    session = await runner.session_service.create_session(app_name="episode", user_id="app")
    message = gt.Content(role="user", parts=[gt.Part(text="start the dinner")])
    for _ in range(4):  # 1 opening leg + 2 resumes + safety margin
        pending = None
        async for ev in runner.run_async(
                user_id="app", session_id=session.id, new_message=message):
            for f in ev.get_function_calls() or []:
                if ev.long_running_tool_ids and f.id in ev.long_running_tool_ids:
                    pending = (f.id, f.name)
        if ep.get("done"):
            return
        if pending is None:
            raise RuntimeError("workflow halted without a resumable request_input")
        # The graph is halted on the RequestInput — wait for the app's button,
        # then answer the pending call.
        action = await wait_for("switch_judge")
        message = gt.Content(role="user", parts=[gt.Part(
            function_response=gt.FunctionResponse(
                id=pending[0], name=pending[1],
                # {"result": <value>} is the wire format the engine unwraps
                # back into the node's plain input (rehydration contract).
                response={"result": action.get("type", "switch_judge")}))])


# ════════════════════════════════════════════════════════════════════

async def run(emit, wait_for):
    if LIVE:
        try:
            await run_workflow(emit, wait_for)
            return
        except Exception as e:
            print(f"[loop] workflow engine failed ({e}); falling back to scripted", flush=True)
            emit("episode_mode", live=False, engine="scripted-fallback")
    await run_scripted(emit, wait_for)
