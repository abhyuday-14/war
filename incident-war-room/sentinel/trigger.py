"""Sentinel — not a long-running agent like the other three. It's the
trigger: read a synthetic monitoring signal, turn it into a crisp alert,
open a Band room, pull in the other three agents plus the on-call human,
and post the alert. Run this once to kick off a demo incident.

This deliberately uses Band's lower-level building blocks (AsyncRestClient +
AgentTools) directly instead of the long-running Agent/adapter loop, because
Sentinel's job is "fire once," not "hold a conversation."

Run from the repo root:
    python sentinel/trigger.py
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from anthropic import AsyncAnthropic

from band import AgentTools
from band.client.rest import AsyncRestClient, ChatRoomRequest
from band.config.loader import load_agent_config

BAND_REST_URL = os.environ.get("BAND_REST_URL", "https://app.band.ai")
ONCALL_HANDLE = os.environ.get("ONCALL_HANDLE", "@oncall")
INCIDENT_PATH = Path(__file__).parent / "synthetic_incident.json"

SENTINEL_SYSTEM_PROMPT = (
    "You are Sentinel, a monitoring agent. Turn the raw signal below into a "
    "crisp incident-room alert: name the affected service, the symptom, "
    "the severity, and the key numbers. Two to four sentences. No preamble, "
    "no markdown headers — this is the first message in a live chat room."
)


async def summarize_alert(client: AsyncAnthropic, raw_signal: dict) -> str:
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=SENTINEL_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(raw_signal, indent=2)}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


async def main() -> None:
    raw_signal = json.loads(INCIDENT_PATH.read_text())

    _sentinel_id, sentinel_key = load_agent_config("sentinel")
    rest = AsyncRestClient(base_url=BAND_REST_URL, api_key=sentinel_key)

    room = await rest.agent_api_chats.create_agent_chat(chat=ChatRoomRequest())
    room_id = room.data.id
    tools = AgentTools(room_id=room_id, rest=rest)

    # Names must match exactly what you named each agent when you created
    # it on app.band.ai (display name, mention, and lookup all key off this).
    for who in ("Triage", "Remediator", "Scribe", ONCALL_HANDLE):
        try:
            await tools.add_participant(who)
        except ValueError as e:
            print(
                f"Couldn't add '{who}': {e}\n"
                "If Sentinel and this peer aren't connected on the platform "
                "yet, send a contact request (or add them to the same Band "
                "workspace) before re-running this script."
            )
            raise

    anthropic_client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env
    alert_text = await summarize_alert(anthropic_client, raw_signal)

    await tools.send_message(alert_text, mentions=["Triage", "Scribe"])

    print(f"Incident room created: {room_id}")
    print("Posted alert. Triage and Scribe mentioned. Watch the room in the Band UI.")


if __name__ == "__main__":
    asyncio.run(main())
