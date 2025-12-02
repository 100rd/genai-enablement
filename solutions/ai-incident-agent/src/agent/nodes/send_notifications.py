"""Notification Sending Node - Placeholder"""

from ..state import AgentState


async def send_notifications(state: AgentState) -> AgentState:
    """Send notifications to channels - TO BE IMPLEMENTED"""
    # TODO: Implement Slack, PagerDuty, MS Teams integration
    state.notification_sent = True
    state.notification_channels = ["slack"]
    return state
