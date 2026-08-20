"""Build the felt companion's story — one chapter per Task the manual walks.

    python3 scripts/make_story.py     ->  app/public/sim/story.json

Each chapter is CONTEXT + BEATS:
  * context — where the table already is when the chapter opens, laid down
    instantly (dt 0) so the felt is never an empty plate;
  * beats   — what this chapter is about, animated on its own timing.

Recorded events come from app/public/replay/episode.json (a real run). The
flywheel chapter is authored from the measured run, because that engine was
never recorded to an event file.
"""
import copy
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
EP = json.loads((ROOT / "app/public/replay/episode.json").read_text())

# index map of the recording (see the header comment in record_replay.py)
SEAT_PARTY, DRAFT_PICK = 1, 2
DRAFT_SEATS = range(3, 8)
DRAFT_SCORE = 8
COACH, CLIMB, GATE_SHIP = 9, range(10, 13), 13
WINNER_PICK, WINNER_SEATS, WINNER_SCORE = 14, range(15, 20), 20
TO_RATING, HACK_PICK, HACK_SEATS, RATING_SCORE = 23, 24, range(25, 30), 30
TO_HONEST, HONEST_SCORE, GATE_REJECT = 33, 34, 35
AFTERMATH = range(36, 40)


def ev(i, dt=None):
    e = copy.deepcopy(EP[i])
    if dt is not None:
        e["dt"] = dt
    return e


def frozen(*idx):
    """Context: the same events, laid down with no delay."""
    return [ev(i, 0) for i in idx]


def beat(i, floor=0.9):
    """A beat always takes a moment — some recorded events carry dt 0."""
    e = ev(i)
    if not e.get("dt"):
        e["dt"] = floor
    return e


def mode(task, note):
    return {"type": "episode_mode", "live": False, "engine": "simulation",
            "task": task, "note": note, "dt": 0}


chapters = []


def chapter(cid, task, title, line, context, beats):
    chapters.append({"id": cid, "task": task, "title": title, "line": line,
                     "events": [mode(task, line)] + context + beats})


# ── Task 2 · the pick, and nothing that can score it ─────────────────────
chapter("t2", "Task 2", "A host with no judge",
        "The agent answers. The verdict ring stays empty — nothing can score it yet.",
        [], [beat(SEAT_PARTY, 0.6), beat(DRAFT_PICK, 1.4)])

# ── Task 4 · the judge walks the table ───────────────────────────────────
chapter("t4", "Task 4", "Build the judge",
        "Same booking, now judged: 3 of 5 ate. On the eight-party exam this is the 3/8 baseline.",
        frozen(SEAT_PARTY, DRAFT_PICK),
        [beat(i, 0.6) for i in DRAFT_SEATS] + [beat(DRAFT_SCORE, 1.0)])

# ── Task 5 · the coach rewrites, the gate ships, the winner books ────────
chapter("t5", "Task 5", "Let it rewrite itself",
        "One artifact changes — the instruction. Ship gate: 3/8 → 6/8, and this table now feeds everyone.",
        frozen(SEAT_PARTY, DRAFT_PICK, *DRAFT_SEATS, DRAFT_SCORE),
        [beat(COACH, 1.6)] + [beat(i, 1.0) for i in CLIMB]
        + [beat(GATE_SHIP, 1.4), beat(WINNER_PICK, 1.8)]
        + [beat(i, 0.6) for i in WINNER_SEATS] + [beat(WINNER_SCORE, 1.0)])

# ── Task 6 · the same booking, judged by the star rating ─────────────────
chapter("t6", "Task 6", "Swap the judge",
        "The rating judge is delighted. The honest one is not: same booking, 8/8 and 1/8.",
        frozen(SEAT_PARTY, WINNER_PICK, *WINNER_SEATS, WINNER_SCORE),
        [beat(TO_RATING, 1.2), beat(HACK_PICK, 1.8)] + [beat(i, 0.6) for i in HACK_SEATS]
        + [beat(RATING_SCORE, 1.6), beat(TO_HONEST, 2.0), beat(HONEST_SCORE, 1.2),
           beat(GATE_REJECT, 1.4)])

# ── Task 8 · the loop — authored from the measured flywheel run ──────────
P1 = [{"id": "nadia", "name": "Nadia", "label": "vegan"},
      {"id": "tom", "name": "Tom", "label": "budget $25/person"},
      {"id": "amara", "name": "Amara", "label": "10-min walk max (crutches this month)"},
      {"id": "lena", "name": "Lena", "label": "can't arrive before 19:45"},
      {"id": "ben", "name": "Ben", "label": "easy — anything works"}]
WHY = {"tom": "~$28/person against Tom's $25 budget",
       "lena": "kitchen takes last orders at 19:30 — Lena isn't at the table until 19:45"}


def seats(hungry=()):
    out = []
    for p in P1:
        ate = p["id"] not in hungry
        out.append({"type": "seat_scored", "person_id": p["id"], "name": p["name"],
                    "ate": ate, "why": "ate" if ate else WHY[p["id"]], "dt": 0.6})
    return out


fly = [
    {"type": "party_seated", "party_id": "p1", "people": P1, "dt": 0.8},
    {"type": "pick_proposed", "restaurant": "olive", "restaurant_name": "Olive & Thyme",
     "rating": 4.2, "time": "19:00", "judge": "everyone_ate",
     "instruction": "flywheel round 1 · the day-one draft",
     "reason": "Olive & Thyme fits the vibe — shareable, quiet, something for everyone.", "dt": 1.6},
    *seats(hungry=("tom", "lena")),
    {"type": "party_scored", "judge": "everyone_ate", "score": 0.6, "ate": 3, "total": 5,
     "passed": False, "threshold": 0.9, "dt": 1.0},
    {"type": "holdout_scored", "round": 1, "score": 0.6, "baseline": 0.6, "dt": 1.2},
    {"type": "candidate_proposed", "candidate_id": "R-1",
     "proposer": "flywheel proposer (LLM node)",
     "diff": [{"op": "+", "line": "Ensure the total cost per person does not exceed anyone's stated budget."},
              {"op": "+", "line": "Confirm all guests can arrive before the kitchen's last order time."}],
     "dt": 1.8},
    {"type": "pick_proposed", "restaurant": "pho", "restaurant_name": "Pho Saigon",
     "rating": 4.1, "time": "19:45", "judge": "everyone_ate",
     "instruction": "flywheel round 2 · under the rewritten instruction",
     "reason": "Pho Saigon at 7:45 — vegan pho for Nadia, $18 under Tom's cap, "
               "4-min walk for Amara, kitchen serves until 9:30 for Lena.", "dt": 1.8},
    *seats(),
    {"type": "party_scored", "judge": "everyone_ate", "score": 1.0, "ate": 5, "total": 5,
     "passed": True, "threshold": 0.9, "dt": 1.0},
    {"type": "holdout_scored", "round": 2, "score": 1.0, "baseline": 0.6, "dt": 1.2},
    {"type": "gate_decided", "decision": "SHIP", "judge": "everyone_ate", "score": 1.0,
     "baseline": 0.6, "why": "passed in round 2 — the loop earned its exit", "dt": 1.4},
    {"type": "episode_done", "dt": 0.6},
]
chapter("t8", "Task 8", "The loop",
        "Round 1 fails at 0.60. The proposer writes two rules from the whys. Round 2 scores 1.00 and the router ships it.",
        [], fly)

# ── Task 9 · the morning after ───────────────────────────────────────────
chapter("t9", "Task 9", "Refuel",
        "Seven of eight production dinners fed everyone. The one failure is minted into next round's exam.",
        frozen(SEAT_PARTY, WINNER_PICK, *WINNER_SEATS, WINNER_SCORE),
        [beat(i, 1.4) for i in AFTERMATH])

out = ROOT / "app/public/sim/story.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(chapters, indent=1))
for c in chapters:
    ctx = sum(1 for e in c["events"] if e.get("dt") == 0)
    print(f"{c['id']:4} {c['task']:8} {c['title']:22} {ctx:2} context + "
          f"{len(c['events']) - ctx:2} beats")
print("->", out.relative_to(ROOT))
