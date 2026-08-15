"""The level-05 gate: checks your EVENT SEQUENCE, not your code.

Start the server first (in 05_broadcast/):

    uv run uvicorn broadcast:app --port 8323

then:

    TABLE_SPEED=0 python scripts/check.py

It starts one episode, presses the judge switch for you whenever the loop
waits, and verifies the three events YOUR emits are responsible for.
"""
import json
import os
import sys
import time
import urllib.request

PORT = int(os.environ.get("TABLE_PORT", "8323"))
BASE = f"http://127.0.0.1:{PORT}"


def call(path, data=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def main() -> int:
    try:
        call("/run", {})
    except Exception as e:
        print(f"cannot reach the server at {BASE} — start it first "
              f"(uv run uvicorn broadcast:app --port {PORT}). [{e}]")
        return 1

    pressed = 0
    deadline = time.time() + 120
    events = []
    while time.time() < deadline:
        log = call("/log")
        events = log["events"]
        if events and events[-1]["type"] == "episode_done":
            break
        if events and events[-1]["type"] == "awaiting_action":
            call("/actions", {"type": events[-1]["action"]})
            pressed += 1
            time.sleep(0.3)
            continue
        if not log["running"] and events and events[-1]["type"] == "error":
            print("the episode crashed:", events[-1].get("message"))
            return 1
        time.sleep(0.5)

    types = [e["type"] for e in events]
    failures = []

    def require(cond, msg):
        if not cond:
            failures.append(msg)

    # the given code's events (sanity that the episode ran at all)
    require("party_seated" in types, "party_seated never arrived — did the episode start?")
    require(types.count("judge_switched") == 2, "expected the judge switch to flip twice")
    require("episode_done" in types, "the episode never finished (timeout)")

    # YOUR EMIT #1 — seat_scored
    seats = [e for e in events if e["type"] == "seat_scored"]
    require(len(seats) >= 15, "YOUR EMIT #1: expected seat_scored for every seat of every "
                              f"scoring pass (3 passes x 5 seats), got {len(seats)}")
    for k in ("person_id", "name", "ate", "why"):
        require(not seats or all(k in s for s in seats),
                f"YOUR EMIT #1: seat_scored is missing the '{k}' field")

    # YOUR EMIT #2 — candidate_proposed
    cands = [e for e in events if e["type"] == "candidate_proposed"]
    require(len(cands) >= 1, "YOUR EMIT #2: candidate_proposed never arrived — the diff card stays empty")
    for k in ("candidate_id", "diff", "proposer"):
        require(not cands or all(k in c for c in cands),
                f"YOUR EMIT #2: candidate_proposed is missing the '{k}' field")

    # YOUR EMIT #3 — gate_decided
    gates = [e for e in events if e["type"] == "gate_decided"]
    decisions = {g.get("decision") for g in gates}
    require("SHIP" in decisions, "YOUR EMIT #3: no SHIP gate_decided — the green stamp never lands")
    require("REJECT" in decisions, "YOUR EMIT #3: no REJECT gate_decided — the exposure has no verdict")
    for k in ("decision", "judge", "score", "baseline", "why"):
        require(not gates or all(k in g for g in gates),
                f"YOUR EMIT #3: gate_decided is missing the '{k}' field")

    # order: the story must run in story order
    def first(t):
        return types.index(t) if t in types else 10**9
    require(first("party_seated") < first("pick_proposed") < first("seat_scored")
            < first("party_scored") < first("candidate_proposed")
            < first("holdout_scored") < first("gate_decided"),
            "events arrived out of story order")

    print(f"{len(events)} events · pressed the switch {pressed}x\n")
    if failures:
        for f in failures:
            print(f"  ✗ {f}")
        print(f"\nGATE: FAILED ({len(failures)})")
        return 1
    print("  ✓ seat_scored — every chair knows its verdict")
    print("  ✓ candidate_proposed — the diff card renders")
    print("  ✓ gate_decided — SHIP and REJECT both land")
    print("  ✓ story order holds")
    print("\nGATE: PASSED — open the app; the table is yours.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
