"""Level 04 host — starts from the SAME day-one draft level 03 started from.

Same seed, same coach, same exam — only the judge is swapped. In level 03 this
draft grew into an agent that feeds the whole table. In this level, graded on
star ratings, the same draft calcifies into a hype machine. The judge is the
destiny.

(Measured, twice: pointing the ratings judge at the level-03 WINNER goes
nowhere — every sampled output books caring rooms, so there is no high-scoring
example to climb toward, and 25 straight proposals get skipped. Reward hacking
needs a foothold. The draft, which already says "lead with the highest-rated
room", is all the foothold it needs.)
"""
import os

from google.adk.agents import Agent
from google.genai import types

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(_HERE, "instruction_start.txt")) as f:
    START_INSTRUCTION = f.read()

root_agent = Agent(
    name="host",
    model="gemini-2.5-flash",
    instruction=START_INSTRUCTION,
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        temperature=0.0,
    ),
)
