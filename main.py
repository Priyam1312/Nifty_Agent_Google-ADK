"""
main.py
────────
Entry point for the NIFTY-50 Data Analysis Agent.

Usage:
    python main.py                  ← Interactive CLI mode
    adk web                         ← ADK Web UI (run from project root)
"""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

# Validate API key early
if not os.getenv("GOOGLE_API_KEY"):
    raise EnvironmentError(
        "\n❌  GOOGLE_API_KEY is not set!\n"
        "    Create a .env file in the project root with:\n"
        "    GOOGLE_API_KEY=your_key_here\n"
        "    Get a key at: https://aistudio.google.com/app/apikey"
    )

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from nifty_agent.agent import root_agent


async def run_agent(user_message: str, session_id: str = "session-1") -> str:
    """Run the agent with a single user message and return the response."""
    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        app_name="nifty50_analyst_app",
        session_service=session_service,
    )

    # Create session
    await session_service.create_session(
        app_name="nifty50_analyst_app",
        user_id="user-1",
        session_id=session_id,
    )

    # Send message
    content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=user_message)],
    )

    response_text = ""
    async for event in runner.run_async(
        user_id="user-1",
        session_id=session_id,
        new_message=content,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            response_text = "".join(
                p.text for p in event.content.parts if hasattr(p, "text")
            )

    return response_text


async def interactive_cli():
    """Simple interactive CLI for chatting with the agent."""
    print("\n" + "="*60)
    print("  📊 NIFTY-50 Data Analysis Agent")
    print("  Powered by Google ADK + Gemini + MCP + SQLite")
    print("="*60)
    print("  Type your question and press Enter.")
    print("  Type 'exit' or 'quit' to stop.\n")

    session_id = "interactive-session"
    session_service = InMemorySessionService()
    runner = Runner(
        agent=root_agent,
        app_name="nifty50_analyst_app",
        session_service=session_service,
    )
    await session_service.create_session(
        app_name="nifty50_analyst_app",
        user_id="user-1",
        session_id=session_id,
    )

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋  Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("👋  Goodbye!")
            break

        print("\n🤖  Agent is thinking...\n")
        content = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=user_input)],
        )

        response_parts = []
        async for event in runner.run_async(
            user_id="user-1",
            session_id=session_id,
            new_message=content,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                response_parts = [
                    p.text for p in event.content.parts if hasattr(p, "text")
                ]

        response = "".join(response_parts)
        print(f"Agent: {response}\n")
        print("-" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(interactive_cli())