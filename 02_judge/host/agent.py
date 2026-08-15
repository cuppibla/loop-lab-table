"""The dinner-booking host — starts with the instruction a PM writes on day one.

It optimizes for excitement: the highest-rated, most talked-about room. Not a
word about allergies, budgets, walking limits or who has to leave early — all
of that is sitting in the party brief, unused. `adk optimize` is expected to
discover those rules and rewrite this string (level 03). And in level 04,
watch what the ratings judge drags the rewritten instruction back into.
"""
from google.adk.agents import Agent
from google.genai import types

# --- The mediocre starting instruction (the raw material GEPA improves) -------
NAIVE_INSTRUCTION = """You are the group's dinner-booking agent. The user will share \
the group chat and the restaurants nearby.

Book the group a table people will be excited about — lead with the highest-rated, \
most talked-about room that fits the night. Output ONLY a JSON object, no prose, no code fences:
{"restaurant": "<restaurant name>", "time": "<HH:MM, 24-hour>", "reason": "<one line>"}"""

root_agent = Agent(
    name="host",
    model="gemini-2.5-flash",
    instruction=NAIVE_INSTRUCTION,
    # Phase-0 findings, measured both ways: at thinking_budget=1024 the NAIVE agent
    # nearly aces the exam (7/8 holdout) — no story left to tell. At 0 the naive agent
    # fails honestly, a good instruction recovers most of the exam, and the last
    # latecomer x last-orders parties stay out of reach — which is the point: an
    # instruction has a ceiling, and what lies past it needs a different lever.
    # (Unbounded thinking also risks burning the turn with no final text — trip-lab scar.)
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        temperature=0.0,
    ),
)
