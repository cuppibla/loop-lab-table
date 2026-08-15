# Table for N — eval as the gate, self-evolution as the loop

One app. One table. N people. An agent picks the restaurant —
**how many of them actually get to eat?**

This repo is the hands-on lab behind that question: a deterministic judge that
walks the table seat by seat, a real `adk optimize` (GEPA) run that rewrites the
agent's own instruction from its scored failures, a reward-hacking study where
swapping the judge for the star rating is *measured* rather than asserted, a
bounded self-evolving loop as an ADK 2 `Workflow`, and a finale where real
production dinners become next round's exam.

```python
def everyone_ate(party, pick):     # the honest judge
    ...                            # walks the table, seat by seat

def rating_score(party, pick):     # the gameable judge
    return pick.rating / 5.0       # <- party is never read
```

Your linter will warn you that `party` is unused. That warning is the entire
lesson.

> **One rule to carry through all six levels:** the loop is neutral machinery —
> it pushes up whatever number you hand it. Everything here is about
> *which number you hand it.*

## Setup

```bash
git clone https://github.com/cuppibla/loop-lab-table
cd loop-lab-table
uv sync
cp .env.example .env        # put your AI Studio key in GOOGLE_API_KEY
uv run python scripts/check_key.py
```

`check_key.py` makes one real model call and tells you plainly whether you are
ready. Levels 01–05 need nothing but that key — no Cloud project, no billing.
Level 06 is the only one that costs money, and it says so.

**The pin matters.** `uv sync` installs `google-adk[eval]==2.3.0`; every
measured number in this lab was produced on that exact version. The ADK 2 line
is not one behavior surface — `mode="task"` can be a workflow-graph node on
2.5.0 but not on 2.0.0b1–2.3.0, which is why the human pause in level 05 uses
`RequestInput`, the door that works across versions.

## The world

Everything the agent books against lives in one file — `world.py`: ten people
with real constraints, ten restaurants, sixteen parties (8 train / 8 holdout),
and **both judges**.

```bash
python3 world.py                    # the signature case
python3 scripts/verify_world.py     # the full sanity suite
python3 scripts/naive_baseline.py   # what the day-one instruction scores
```

The world is adversarial on purpose: the highest-rated room in the district
(★4.9) is the one that reliably leaves people hungry, while the answers that
feed everyone sit mid-pack at ★4.0–4.2.

## The six levels

Each level is a folder, and each adds exactly one idea — `diff` two neighboring
levels and you are reading the lesson.

| | folder | what it adds |
|---|---|---|
| 01 | `01_host/` | a working agent with the instruction a PM writes on day one — and no way to tell whether its answer is good |
| 02 | `02_judge/` | `everyone_ate` as a custom `adk eval` metric. **Ships deliberately broken** — the two-line fix is yours |
| 03 | `03_optimize/` | `adk optimize` (GEPA) rewrites the instruction from the judge's reasons; a ship gate on parties it never saw |
| 04 | `04_reward_hacking/` | the same coach pointed at star ratings — four measured runs, and an honest re-test of what it built |
| 05 | `05_broadcast/` | the loop as a typed event stream: an ADK 2 `Workflow` with human-in-the-loop, plus a bounded self-evolving `flywheel` |
| 06 | `06_refuel/` | deploy for real, watch two pipes (Cloud Trace + BigQuery), and mint production failures into the next exam |

Levels 02 and 05 ship with holes on purpose (`# ── YOUR FIX ──`,
`# ── YOUR EMIT #n ──`); `solutions/` and `prebaked/` sit next to them when you
want the answer or want to skip an expensive run.

## The app

`app/` is a Next.js stage that renders the loop — seats fold as the judge walks
the table, the diff card shows the rewrite, the switch flips the judge live.

```bash
cd app && npm install && npm run dev     # http://localhost:3260
```

It runs from a recording out of the box (no key needed). To drive it from real
model calls, start the broadcast server next to it:

```bash
cd 05_broadcast
RUNNER=solutions TABLE_LIVE=1 uv run uvicorn broadcast:app --port 8323
```

Swap `RUNNER=flywheel` to watch the bounded self-evolving loop rewrite its own
instruction, round by round.
