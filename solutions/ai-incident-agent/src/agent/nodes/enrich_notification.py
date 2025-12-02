"""Notification Enrichment Node - Placeholder"""

from ..state import AgentState


async def enrich_notification(state: AgentState) -> AgentState:
    """Create enriched notification - TO BE IMPLEMENTED"""
    # TODO: Generate human-friendly notification with LLM
    state.next_step = "send_notifications"
    return state
