"""Triage agent — correlates the alert against logs, metrics, and deploys,
then hands off to Remediator. Built on LangGraph via band-sdk's
LangGraphAdapter.

Run from the repo root:
    python triage/agent.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from langchain_anthropic import ChatAnthropic
from langgraph.checkpoint.memory import InMemorySaver

from band import Agent
from band.adapters.langgraph import LangGraphAdapter

from tools import correlate_deploys, query_logs, query_metrics

BAND_REST_URL = os.environ.get("BAND_REST_URL", "https://app.band.ai")
BAND_WS_URL = os.environ.get("BAND_WS_URL", "wss://app.band.ai/api/v1/socket/websocket")
ROLE_PROMPT = (Path(__file__).parent / "prompts" / "role.md").read_text()


async def main() -> None:
    adapter = LangGraphAdapter(
        llm=ChatAnthropic(model="claude-sonnet-4-6"),
        checkpointer=InMemorySaver(),
        custom_section=ROLE_PROMPT,
        additional_tools=[query_metrics, query_logs, correlate_deploys],
    )

    agent = Agent.from_config(
        name="triage",
        adapter=adapter,
        ws_url=BAND_WS_URL,
        rest_url=BAND_REST_URL,
    )

    print("Triage agent connecting to Band...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
