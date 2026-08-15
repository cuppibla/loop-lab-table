"""Shared decision parsing for scripts (same rules as metrics/table.py)."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

_TIME_RE = re.compile(r"^\s*(\d{1,2}:\d{2})")


def parse_decision(text: str):
    """raw model text -> (restaurant_id | None, 'HH:MM')."""
    import world
    cleaned = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    decision = None
    try:
        decision = json.loads(cleaned)
    except Exception:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                decision = json.loads(m.group(0))
            except Exception:
                decision = None
    if not isinstance(decision, dict):
        return None, "19:00"
    rid = world.find_restaurant(str(decision.get("restaurant", "")))
    m = _TIME_RE.match(str(decision.get("time", "")))
    return rid, (m.group(1) if m else "19:00")
