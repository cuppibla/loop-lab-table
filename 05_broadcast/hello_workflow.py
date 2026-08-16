"""Your first ADK 2 Workflow — four nodes, one of each kind, one file.

    seat_party   function node   puts tonight's brief into STATE
    confirm      RequestInput    the graph SUSPENDS until you press Enter
    host         agent node      one live model call — books the table
    judge        function node   everyone_ate scores what got booked

Run it (needs GOOGLE_API_KEY; one model call):

    uv run python hello_workflow.py
"""
from __future__ import annotations

import asyncio
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from dotenv import load_dotenv

load_dotenv(os.path.join(_HERE, "..", ".env"))
if os.environ.get("GOOGLE_API_KEY"):
    # an AI Studio key wins locally; without one, Vertex mode is respected
    os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)

from google.adk import Agent, Event, Workflow  # noqa: E402
from google.adk.events import RequestInput  # noqa: E402
from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types as gt  # noqa: E402

import world  # noqa: E402
from loop_runner import parse_decision  # noqa: E402  (plumbing: text -> pick)

PARTY = "p1"


# ── node 1 · a FUNCTION node: deterministic code that writes STATE ──
def seat_party(node_input: str):
    people = [world.PEOPLE[i]["name"] for i in world.PARTIES[PARTY]]
    print(f"— seat_party: {', '.join(people)} sit down")
    yield Event(state={"brief": world.brief(PARTY)})


# ── node 2 · a RequestInput: the graph HALTS here (not a sleep — suspended) ──
def confirm(node_input=None):
    yield RequestInput(message="Send the host to book?")


# ── node 3 · an AGENT node: one live model call. Note the {brief} template —
#             it is resolved from STATE at call time. ──
host = Agent(
    name="host", model="gemini-2.5-flash",
    instruction=open(os.path.join(_HERE, "instruction_draft.txt")).read()
    + "\n\nHere is tonight's request:\n{brief}",
    output_key="decision",
    generate_content_config=gt.GenerateContentConfig(
        thinking_config=gt.ThinkingConfig(thinking_budget=0), temperature=0.0))


# ── node 4 · a FUNCTION node again: its argument name `decision` pulls the
#             agent's output_key straight out of state ──
def judge(decision: str):
    rid, t, _ = parse_decision(decision)
    score, seats = world.everyone_ate(world.PARTIES[PARTY], rid, t)
    verdict = "PASSED" if score >= world.THRESHOLD else "FAILED"
    print(f"— host booked: {world.RESTAURANTS[rid]['name']} @ {t}")
    print(f"— judge: {score:.2f} {verdict}")
    for s in seats:
        if not s["ate"]:
            print(f"    {s['name']}: {s['why']}")
    yield Event(message="done")


# ── the graph. That's it: nodes, in an edge. ──
hello = Workflow(name="hello", edges=[("START", seat_party, confirm, host, judge)])


async def main():
    runner = InMemoryRunner(agent=hello, app_name="hello")
    session = await runner.session_service.create_session(app_name="hello", user_id="you")
    message = gt.Content(role="user", parts=[gt.Part(text="dinner time")])
    for _ in range(2):  # leg 1 runs until the pause; leg 2 after your Enter
        pending = None
        async for ev in runner.run_async(user_id="you", session_id=session.id,
                                         new_message=message):
            for f in ev.get_function_calls() or []:
                if ev.long_running_tool_ids and f.id in ev.long_running_tool_ids:
                    pending = (f.id, f.name)
        if pending is None:
            return  # the judge ran; the graph reached its end
        input("⏸  the graph is SUSPENDED. Press Enter to resume: ")
        # the resume contract: answer the pending call, wire format {"result": ...}
        message = gt.Content(role="user", parts=[gt.Part(
            function_response=gt.FunctionResponse(
                id=pending[0], name=pending[1], response={"result": "go"}))])


if __name__ == "__main__":
    asyncio.run(main())
