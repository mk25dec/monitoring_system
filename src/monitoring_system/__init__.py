"""Local stage monitoring: emit from any Python job, view in Streamlit."""

from monitoring_system.client import StageClient, emit, get_client, next_sequence, track

__all__ = [
    "StageClient",
    "emit",
    "get_client",
    "next_sequence",
    "track",
]

__version__ = "0.1.0"
