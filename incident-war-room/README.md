# Incident War Room — a regulated multi-agent SRE workflow on Band

Four agents share one live Band room during a production incident instead of
a human bouncing between a dashboard, a Slack thread, and a status page.

- **Sentinel** — detects the anomaly, opens the Band room, and posts the
  first message with the raw signal.
- **Triage** (LangGraph) — correlates the alert against recent deploys/logs
  and posts a root-cause hypothesis with a confidence level.
- **Remediator** (Claude Agent SDK) — drafts a fix and can only execute it
  after a human on-call engineer types `/approve` in the same room. It only
  has the tool it needs (`apply_remediation`); it never gets broader access
  than the on-call engineer explicitly grants.
- **Scribe** (Claude/Anthropic) — once the incident is marked resolved, reads
  the *entire* Band room transcript via the platform's own context API and
  drafts a blameless postmortem from it — not from its own chat memory.

Why this is more than a notification bot: the four agents are reacting to
the same live room in real time, Remediator's authority is enforced by
Band's chat-based tool-approval gate (not by trusting the model), and the
postmortem is generated *from* Band's stored room context, so the room
itself is the system of record for the incident.

## Architecture

```
                 ┌───────────────────────────────────────────┐
                 │              Band chat room                │
                 │                                             │
  Sentinel ──────▶  alert posted, @Triage mentioned            │
                 │        │                                    │
                 │        ▼                                    │
                 │  Triage (LangGraph) ── hypothesis ──▶ @Remediator
                 │                                             │
                 │  Remediator (Claude SDK) ── proposes fix    │
                 │        │  tool call gated by /approve       │
                 │        ▼                                    │
                 │  On-call human types /approve or /decline   │
                 │        │                                    │
                 │        ▼                                    │
                 │  "incident resolved" ──▶ @Scribe             │
                 │                                             │
                 │  Scribe ── fetch_room_context ── postmortem │
                 └───────────────────────────────────────────┘
```

## 0. Prerequisites

- Python 3.11+ and `uv` (or plain `pip`)
- An Anthropic API key (Triage's LLM calls, Remediator, Scribe)
- Four agents created on the Band platform (app.band.ai), named **exactly**
  `Sentinel`, `Triage`, `Remediator`, `Scribe` — mention resolution and
  participant lookup both key off this display name. Creating each one
  gives you an **agent UUID** and an **API key**; you need both for every
  agent. Make sure Sentinel has a peer/contact relationship with the other
  three (and with your own account) on the platform — `add_participant`
  can only add peers Sentinel can already see.

## 1. Install

This repo intentionally keeps each agent's dependencies separate, the same
way you'd deploy them as separate services in production.

```bash
git clone <this repo> incident-war-room && cd incident-war-room

# one venv is fine for a demo; in production each agent ships its own image
python3 -m venv .venv && source .venv/bin/activate

pip install -r triage/requirements.txt
pip install -r remediator/requirements.txt
pip install -r scribe/requirements.txt
pip install -r sentinel/requirements.txt
```

(`band-sdk` is on PyPI; add `--break-system-packages` to each command if
you're installing outside a venv.)

## 2. Configure

```bash
cp .env.example .env                       # fill in ANTHROPIC_API_KEY, ONCALL_HANDLE
cp agent_config.yaml.example agent_config.yaml   # paste in your 4 agent_id/api_key pairs
```

`agent_config.yaml` lives at the repo root. Every agent script reads it
relative to your current working directory, so always run commands from
the repo root.

## 3. Run it

Four long-running processes, one per terminal, all from the repo root:

```bash
python triage/agent.py
python remediator/agent.py
python scribe/agent.py
```

Then fire the synthetic incident:

```bash
python sentinel/trigger.py
```

Sentinel will create a room, add Triage/Remediator/Scribe and your on-call
handle as participants, and post the alert. Watch Triage hand off to
Remediator, approve or decline the proposed fix with `/approve` or
`/decline` in the room, then post `@Scribe incident resolved, please write
the postmortem` to trigger the final step.

## Where the "regulated workflow" framing comes from

Remediator is configured with `approval_mode="manual"` and
`approval_authorized_senders={ONCALL_HANDLE}`. Every tool call it makes —
including the custom `apply_remediation` tool, not just file edits — is
intercepted by Band's chat-based approval hook and held until the named
on-call handle approves or declines it in the room. That's the enforcement
point: Remediator can *propose* anything, but the blast radius of what it
can *do* is bounded by who's allowed to say `/approve`.

## Swap the demo pieces for real ones

- `triage/tools.py` simulates `query_logs` / `correlate_deploys`; point
  these at your real observability stack (Datadog, Honeycomb, your deploy
  log) and the rest of the workflow is unchanged.
- `remediator/tools.py` simulates `apply_remediation`; replace the body
  with your actual rollback/scale/feature-flag API call. The approval gate
  in front of it doesn't change.
- `sentinel/trigger.py` reads a static JSON payload; wire it to a real
  PagerDuty/Datadog webhook receiver instead.
