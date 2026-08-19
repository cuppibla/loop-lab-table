"""Run the host on one party. Usage: python run.py p3"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"), override=True)
if os.environ.get("GOOGLE_API_KEY"):
    # an AI Studio key wins locally; without one, Vertex mode is respected
    os.environ.pop("GOOGLE_GENAI_USE_VERTEXAI", None)
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
import world
from host import root_agent


def print_brief(party_id):
    """--brief: print the party brief for copy-pasting into adk web."""
    print(world.brief(party_id))


async def main(party_id):
    svc = InMemorySessionService()
    await svc.create_session(app_name="host", user_id="you", session_id="s1")
    runner = Runner(agent=root_agent, app_name="host", session_service=svc)
    async for ev in runner.run_async(user_id="you", session_id="s1",
            new_message=types.Content(role="user", parts=[types.Part(text=world.brief(party_id))])):
        if ev.is_final_response():
            print(ev.content.parts[0].text)


if "--brief" in sys.argv:
    print_brief(next((a for a in sys.argv[1:] if not a.startswith("-")), "p3"))
else:
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "p3"))
