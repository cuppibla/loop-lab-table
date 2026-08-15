"""Generate the two exams from world.py. Re-run after ANY world edit.

  parties_train.evalset.json — 8 parties the optimizer will see
  parties_val.evalset.json   — 8 parties it never will (36 seats)

Note "final_response": null — there is no golden answer, because the judge is
a checker function: whatever the agent answers, it can be graded. (This is
also what makes level 06 possible.)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import world  # noqa: E402


def make(name: str, party_ids: list[str]) -> dict:
    return {
        "eval_set_id": name,
        "name": name,
        "eval_cases": [
            {
                "eval_id": pid,
                "conversation": [{
                    "invocation_id": f"inv-{pid}",
                    "user_content": {"parts": [{"text": world.brief(pid)}], "role": "user"},
                    "final_response": None,
                    "intermediate_data": None,
                }],
                "session_input": {"app_name": "host", "user_id": "lab", "state": {}},
            }
            for pid in party_ids
        ],
        "creation_timestamp": 0.0,
    }


here = os.path.dirname(__file__)
for name, ids in [("parties_train", world.TRAIN), ("parties_val", world.HOLDOUT)]:
    path = os.path.join(here, "host", f"{name}.evalset.json")
    with open(path, "w") as f:
        json.dump(make(name, ids), f, indent=2)
    print(f"wrote {path}  ({len(ids)} cases)")
