"""Context Gathering Node - Placeholder"""

from ..state import AgentState, IncidentStatus


async def gather_context(state: AgentState) -> AgentState:
    """Gather context (logs, metrics, traces) - TO BE IMPLEMENTED"""
    state.status = IncidentStatus.GATHERING_CONTEXT
    # TODO: Implement CloudWatch Logs, Metrics, X-Ray integration
    state.context_gathering_complete = True
    state.next_step = "analyze_incident"
    return state
