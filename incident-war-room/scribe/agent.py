"""Scribe agent — a custom SimpleAdapter (not one of the framework adapters)
because its job needs direct access to Band's own room-context API, not a
chat-completion tool loop.

Design note on why every other agent CCs @Scribe on every handoff message:
Band's fetch_room_context() is intentionally scoped to "messages this agent
sent, or was @mentioned in" -- it's an agent-relevant context endpoint, not
a raw firehose of every message in the room. So Scribe only gets a complete
picture of the incident if it's mentioned on every handoff. That's exactly
what Triage's and Remediator's role prompts ask them to do: mention the
next responsible agent *and* @Scribe, the same way you'd cc someone on an
email thread you want them to have full visibility into without acting on.

Run from the repo root:
    python scribe/agent.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from anthropic import AsyncAnthropic

from band import Agent
from band.core.simple_adapter import SimpleAdapter
from band.core.types import PlatformMessage
from band.core.protocols import AgentToolsProtocol

BAND_REST_URL = os.environ.get("BAND_REST_URL", "https://app.band.ai")
BAND_WS_URL = os.environ.get("BAND_WS_URL", "wss://app.band.ai/api/v1/socket/websocket")
ONCALL_HANDLE = os.environ.get("ONCALL_HANDLE", "@oncall")
ROLE_PROMPT = (Path(__file__).parent / "prompts" / "role.md").read_text()

# Heuristic resolution trigger for the demo. In production, swap this for a
# structured signal -- e.g. Remediator firing a send_event(message_type="task")
# when the fix is confirmed -- rather than matching on free text.
RESOLUTION_KEYWORDS = ("resolved", "postmortem", "write up", "write-up", "close the incident")


def _looks_like_resolution_trigger(content: str) -> bool:
    lowered = content.lower()
    return any(kw in lowered for kw in RESOLUTION_KEYWORDS)


async def _fetch_full_transcript(tools: AgentToolsProtocol, room_id: str) -> str:
    """Page through every message Scribe was CC'd on and render it as a
    plain-text timeline for the postmortem prompt."""
    lines: list[str] = []
    page = 1
    while True:
        result = await tools.fetch_room_context(room_id=room_id, page=page, page_size=100)
        for item in result["data"]:
            sender = item.get("sender_name") or item.get("sender_type") or "unknown"
            lines.append(f"[{item.get('inserted_at')}] {sender}: {item.get('content')}")
        meta = result["meta"]
        if page >= meta.get("total_pages", 1):
            break
        page += 1
    return "\n".join(lines)


class ScribeAdapter(SimpleAdapter[None]):
    def __init__(self, anthropic_client: AsyncAnthropic, role_prompt: str):
        super().__init__(history_converter=None)
        self._client = anthropic_client
        self._role_prompt = role_prompt

    async def on_message(
        self,
        msg: PlatformMessage,
        tools: AgentToolsProtocol,
        history: None,
        participants_msg: str | None,
        contacts_msg: str | None,
        *,
        is_session_bootstrap: bool,
        room_id: str,
    ) -> None:
        if not _looks_like_resolution_trigger(msg.content):
            # CC'd on a handoff message Scribe doesn't need to act on yet.
            return

        transcript = await _fetch_full_transcript(tools, room_id)

        response = await self._client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=self._role_prompt,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Here is the full incident room transcript. Write the "
                        "postmortem now.\n\n---\n" + transcript
                    ),
                }
            ],
        )
        postmortem = "".join(
            block.text for block in response.content if block.type == "text"
        )
        await tools.send_message(postmortem, mentions=[ONCALL_HANDLE])


async def main() -> None:
    client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env
    adapter = ScribeAdapter(anthropic_client=client, role_prompt=ROLE_PROMPT)

    agent = Agent.from_config(
        name="scribe",
        adapter=adapter,
        ws_url=BAND_WS_URL,
        rest_url=BAND_REST_URL,
    )

    print("Scribe agent connecting to Band (silent until incident is marked resolved)...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
