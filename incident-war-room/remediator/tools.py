"""The one action Remediator is allowed to take. Replace the body with a
real call to your deploy/rollback/feature-flag API — the approval gate in
front of it (configured on the ClaudeSDKAdapter in agent.py) doesn't change.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ApplyRemediationInput(BaseModel):
    action: str = Field(
        description=(
            "The remediation to apply, e.g. 'rollback:d-48213', "
            "'scale_out:checkout-api:+3', 'flag_off:new_payment_flow'."
        )
    )
    reason: str = Field(description="One sentence justification tied to Triage's hypothesis.")


def apply_remediation(action: str, reason: str) -> str:
    """Execute a remediation action. Only runs after a human approves the
    tool call in the Band room (see approval_mode on the adapter)."""
    # --- replace this block with a real rollback / scale / flag API call ---
    return f"Applied remediation '{action}'. Reason: {reason}. Status: success (simulated)."
