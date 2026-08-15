"""Level 06 host — the SHIPPED instruction (your level-03 winner), deployed.

This is the whole premise of the level: you ship the good agent, and
production traffic goes looking for the residue the exam missed.
`instruction_shipped.txt` carries our real GEPA winner — replace it with
yours before deploying.
"""
import os

from google.adk.agents import Agent
from google.genai import types

# The instruction ships INSIDE the package — the deploy only uploads host/,
# so a file one level up simply does not exist in the cloud container.
_HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(_HERE, "instruction_shipped.txt")) as f:
    SHIPPED_INSTRUCTION = f.read()

root_agent = Agent(
    name="host",
    model="gemini-2.5-flash",
    instruction=SHIPPED_INSTRUCTION,
    generate_content_config=types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        temperature=0.0,
    ),
)
