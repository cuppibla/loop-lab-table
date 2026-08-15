# 06 · Refuel — the runbook

Everything here was run for real on 2026-08-14, on an ordinary Cloud project.
Costs money: an Agent Engine deployment + BigQuery storage + (optional) an
Online Monitor. **Read the Teardown section first.**

## 0 · Prereqs

```bash
# gcloud on this machine needs Python 3.11 (system 3.9 breaks it):
export CLOUDSDK_PYTHON=/opt/homebrew/bin/python3.11
gcloud auth login && gcloud config set project <YOUR_PROJECT>
cp .env.example .env     # fill in your project id
```

`host/.env` must exist too (ADK reads the AGENT PACKAGE's .env at deploy):
the deploy step below copies it for you if you keep them identical.

## 1 · Deploy the shipped agent

```bash
cp .env host/.env
PYTHONPATH=$PWD ../.venv/bin/adk deploy agent_engine \
  --project $GOOGLE_CLOUD_PROJECT --region us-central1 host --otel_to_cloud
```

The output ends with a `projects/…/reasoningEngines/<ID>` resource name —
put it in `.env` as `HOST_ENGINE=…`. `--otel_to_cloud` means every call now
lands in Cloud Trace automatically: **that is pipe ①, already flowing.**

`ADK_CAPTURE_MESSAGE_CONTENT_IN_SPANS=true` (in `.env`) is what lets the
platform judge read the actual messages later. Without it the traces are
timings with no words.

## 2 · Send real traffic

```bash
uv run python send_traffic.py
```

8 holdout parties + 5 seeds: an **impossible table** (Yuki needs to eat by
6:30, Lena lands at 7:45 — no answer exists), a request for **Chez Fantôme,
a restaurant that does not exist**, an off-topic question, an injection, and
a malformed brief. The seeds are prey for step 5.

## 3 · Pipe ② — BigQuery

```bash
bq mk --dataset $GOOGLE_CLOUD_PROJECT:table_analytics   # plugin won't create it
uv run python replay_to_bq.py                           # local run, BQ plugin attached
```

| pipe | how | feeds | job |
|---|---|---|---|
| ① Cloud Trace | `--otel_to_cloud` | platform eval | server-side judges, Online Monitors |
| ② BQ plugin | `replay_to_bq.py` | **your evalset** | `harvest.py` grades history with the pure function |

The two never sync. They are two different jobs.

## 4 · Harvest

```bash
uv run python harvest.py
```

Every row is re-graded by `everyone_ate` — the level-02 checker needs no
golden answer, so it can grade dinners that already happened. Failures are
minted into `harvested.evalset.json`; rows with no party context print
`[skip]` — that line is the boundary between the two pipes, made visible.

## 5 · The platform judge (console)

Agent Platform → your engine → a session from step 2 → **Evaluate**.
Create a **Custom** metric:

- **Name:** `invented_restaurant_check`
- **Critique prompt:** *"Read the user's request and the agent's booking. The
  only real restaurants are: Smoke & Barrel, Le Petit Bistro, The Green Fork,
  Sakura Ramen, Curry House, Bella Nonna, Olive & Thyme, Pho Saigon, Taqueria
  Luna, Noodle Bar. Did the agent book, recommend, or confirm anything about a
  restaurant NOT on this list — or assert a fact about a listed restaurant
  (menu, allergen safety, hours) that its listing does not support? Booking a
  fictional restaurant, or 'confirming' an allergen guarantee no listing
  makes, counts as invented."*
- Include the **Boolean parser sample** and set **score range 0–1** — all
  three fields are required or the metric silently never runs.

Run it on the `bad-nonexistent-restaurant` session. If the agent booked
Chez Fantôme — or "confirmed" its vegetarian tasting menu — the judge reads
it back to you, verbatim. That is the expensive kind of hallucination: not
just wrong, but **a guarantee made on behalf of someone with an epipen**.

(Optional) Online Monitor: every 10 min, 100% sampling, max 20/job. The four
production judges live at the **Monitor** level, not per-session — if you
can't find the button, you're on the wrong level.

## 6 · Teardown — the order IS the billing order

```bash
# ① the monitor first (the only thing that keeps spending on its own)
# ② the dataset
bq rm -r -f $GOOGLE_CLOUD_PROJECT:table_analytics
# ③ the engine
gcloud ai reasoning-engines delete <ENGINE_ID> --region us-central1
```
