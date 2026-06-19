"""Remediator agent — proposes and (after human /approve) executes a fix.
Built on the Claude Agent SDK via band-sdk's ClaudeSDKAdapter.

The important line is approval_mode="manual": every tool call this agent
makes, including apply_remediation, is held in the Band room until the
on-call handle in ONCALL_HANDLE types /approve or /decline.

Run from the repo root:
    python remediator/agent.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from band import Agent
from band.adapters.claude_sdk import ClaudeSDKAdapter

from tools import ApplyRemediationInput, apply_remediation

BAND_REST_URL = os.environ.get("BAND_REST_URL", "https://app.band.ai")
BAND_WS_URL = os.environ.get("BAND_WS_URL", "wss://app.band.ai/api/v1/socket/websocket")
ONCALL_HANDLE = os.environ.get("ONCALL_HANDLE", "@oncall")
ROLE_PROMPT = (Path(__file__).parent / "prompts" / "role.md").read_text()


async def main() -> None:
    adapter = ClaudeSDKAdapter(
        model="sonnet",
        custom_section=ROLE_PROMPT,
        additional_tools=[(ApplyRemediationInput, apply_remediation)],
        # --- the governance line ---
        approval_mode="manual",
        approval_authorized_senders={ONCALL_HANDLE},
        approval_wait_timeout_s=600.0,
        approval_timeout_decision="decline",
    )

    agent = Agent.from_config(
        name="remediator",
        adapter=adapter,
        ws_url=BAND_WS_URL,
        rest_url=BAND_REST_URL,
    )

    print(f"Remediator agent connecting to Band (approvals authorized: {ONCALL_HANDLE})...")
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
