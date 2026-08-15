"""Level 03 host — its instruction lives in ../instruction_current.txt.

Ships as the day-one draft. After your GEPA run, swap the winner in:

    cp prebaked/instruction_after.txt instruction_current.txt

then relaunch `adk web` and paste the SAME party brief — same prompt,
different answer. Swap back anytime: git checkout instruction_current.txt
"""
import os

from google.adk.agents import Agent
from google.genai import types

_LEVEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

with open(os.path.join(_LEVEL, "instruction_current.txt")) as f:
    CURRENT_INSTRUCTION = f.read()

root_agent = Agent(
    name="host",
    model="gemini-2.5-flash",
    instruction=CURRENT_INSTRUCTION,
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        temperature=0.0,
    ),
)
