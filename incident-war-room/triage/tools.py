"""Simulated observability tools for Triage.

Swap the bodies of these for real calls to your metrics/log/deploy systems
(Datadog, Honeycomb, your CI/CD log, etc). The signatures and tool framing
are what matters for the rest of the workflow.
"""

from __future__ import annotations

from langchain_core.tools import tool


@tool
def query_metrics(service: str, window_minutes: int = 30) -> str:
    """Pull recent error-rate / latency metrics for a service.

    Args:
        service: Name of the affected service, e.g. "checkout-api".
        window_minutes: How far back to look.
    """
    # Simulated response for the demo. Replace with a real metrics query.
    return (
        f"[metrics] {service}: 5xx rate jumped from 0.2% to 14.8% starting "
        f"~{window_minutes - 6} minutes ago. p99 latency up 3.4x over the same window."
    )


@tool
def query_logs(service: str, query: str = "error") -> str:
    """Search recent application logs for a service.

    Args:
        service: Name of the affected service.
        query: A keyword or pattern to search for in logs.
    """
    return (
        f"[logs] {service}: 412 occurrences of 'connection pool exhausted' "
        f"matching '{query}' in the last 30 minutes, all from the same pod group."
    )


@tool
def correlate_deploys(service: str, window_minutes: int = 60) -> str:
    """Check whether a recent deploy lines up with the start of the anomaly.

    Args:
        service: Name of the affected service.
        window_minutes: How far back to check the deploy log.
    """
    return (
        f"[deploys] {service}: deploy d-48213 (connection pool size change) "
        f"shipped 41 minutes ago, inside the {window_minutes}-minute window."
    )
