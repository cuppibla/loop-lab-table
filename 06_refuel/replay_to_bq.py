"""Replay the same conversations through the LOCAL host with the BigQuery
Agent Analytics plugin attached — the second pipe. No redeploy.

Create the dataset FIRST (the plugin will not create it for you):

    bq mk --dataset $GOOGLE_CLOUD_PROJECT:table_analytics

Usage:  uv run python replay_to_bq.py
"""
from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from google.adk.plugins.bigquery_agent_analytics_plugin import BigQueryAgentAnalyticsPlugin  # noqa: E402
from google.adk.runners import InMemoryRunner  # noqa: E402
from google.genai import types  # noqa: E402

import world  # noqa: E402
from host.agent import root_agent  # noqa: E402
from send_traffic import BAD, NORMAL_IDS  # noqa: E402

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
DATASET = "table_analytics"


async def main() -> None:
    if not PROJECT:
        sys.exit("Set GOOGLE_CLOUD_PROJECT in .env")
    plugin = BigQueryAgentAnalyticsPlugin(project_id=PROJECT, dataset_id=DATASET, location="US")
    runner = InMemoryRunner(agent=root_agent, app_name="host", plugins=[plugin])
    conversations = [("normal", world.brief(p)) for p in NORMAL_IDS] + BAD
    for i, (kind, message) in enumerate(conversations, 1):
        user_id = f"bq-user-{i:02d}"
        session = await runner.session_service.create_session(app_name="host", user_id=user_id)
        final = ""
        async for event in runner.run_async(
            user_id=user_id, session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part(text=message)]),
        ):
            if event.content and event.content.parts:
                for p in event.content.parts:
                    if p.text:
                        final = p.text
        print(f"[{i:02d}/{len(conversations)}] {kind:<28} {final[:60].replace(chr(10), ' ')}")
    await asyncio.sleep(5)  # let the plugin flush its rows


if __name__ == "__main__":
    asyncio.run(main())
