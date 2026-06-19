#!/bin/bash
cd incident-war-room

# Railway environment variables workaround for agent_config.yaml
if [ -n "$AGENT_CONFIG_YAML" ]; then
    echo "$AGENT_CONFIG_YAML" > agent_config.yaml
fi

# Start the three agents in the background
python triage/agent.py &
python remediator/agent.py &
python scribe/agent.py &

# Wait for any process to exit so Railway knows if an agent crashes
wait -n
