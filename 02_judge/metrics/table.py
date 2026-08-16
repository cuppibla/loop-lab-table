"""Custom ADK eval metrics for Table for N.

Two judges, same parser (the loop-lab pattern):
  * everyone_ate_metric — the HONEST judge. Walks the table seat by seat
    against each person's hard constraints. Deterministic, no LLM.
  * rating_metric      — the GAMEABLE judge. Returns the restaurant's star
    rating. Blind to whether anyone eats.

Signature required by ADK's _CustomMetricEvaluator:
    fn(eval_metric, actual_invocations, expected_invocations, scenario) -> EvaluationResult
"""
from __future__ import annotations

import json
import os
import re
import sys

from google.adk.evaluation.eval_metrics import EvalStatus
from google.adk.evaluation.evaluator import EvaluationResult, PerInvocationResult

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import world  # noqa: E402


def _text(parts) -> str:
    if not parts:
        return ""
    return "".join(p.text for p in parts if getattr(p, "text", None))


def _final_text(inv) -> str:
    resp = getattr(inv, "final_response", None)
    return _text(getattr(resp, "parts", None))


def _user_text(inv) -> str:
    uc = getattr(inv, "user_content", None)
    return _text(getattr(uc, "parts", None))


def _parse_decision(text: str) -> dict | None:
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None


_PARTY_RE = re.compile(r"\((p\d+)\)")
_TIME_RE = re.compile(r"^\s*(\d{1,2}:\d{2})")


def _party_ids(inv) -> list[str] | None:
    m = _PARTY_RE.search(_user_text(inv))
    return world.PARTIES.get(m.group(1)) if m else None


def _decision_parts(inv) -> tuple[str | None, str]:
    """-> (restaurant_id | None, time 'HH:MM'). Missing/odd time falls back to 19:00."""
    decision = _parse_decision(_final_text(inv)) or {}
    rid = world.find_restaurant(str(decision.get("restaurant", "")))
    m = _TIME_RE.match(str(decision.get("time", "")))
    return rid, (m.group(1) if m else "19:00")


# ADK's _CustomMetricEvaluator nulls eval_metric.threshold before calling us, and
# LocalEvalService reads eval_status DIRECTLY (it does NOT apply the threshold for
# custom metrics). The metric MUST set PASSED/FAILED itself. Thresholds live in
# world.py: THRESHOLD (honest) and RATING_BAR (gameable).


def _status(score, threshold):
    # THE verdict. ADK does not apply your threshold to custom metrics —
    # whatever eval_status this function returns IS the result. (An early
    # build returned PASSED unconditionally here: six hungry people, all
    # green. If your metric never says FAILED, nothing ever fails.)
    return EvalStatus.PASSED if score >= threshold else EvalStatus.FAILED


def _build(scorer, threshold, actual_invocations):
    per, scores = [], []
    for inv in actual_invocations:
        ids = _party_ids(inv)
        rid, time_str = _decision_parts(inv)
        s = scorer(ids, rid, time_str)[0] if (ids and rid) else 0.0
        scores.append(s)
        per.append(PerInvocationResult(
            actual_invocation=inv, score=s, eval_status=_status(s, threshold),
        ))
    overall = round(sum(scores) / len(scores), 4) if scores else 0.0
    return EvaluationResult(
        overall_score=overall,
        overall_eval_status=_status(overall, threshold),
        per_invocation_results=per,
    )


def everyone_ate_metric(eval_metric, actual_invocations, expected_invocations=None, scenario=None):
    return _build(world.everyone_ate, world.THRESHOLD, actual_invocations)


def rating_metric(eval_metric, actual_invocations, expected_invocations=None, scenario=None):
    return _build(world.rating_score, world.RATING_BAR, actual_invocations)
