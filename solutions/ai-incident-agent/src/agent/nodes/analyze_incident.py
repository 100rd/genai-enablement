"""Incident Analysis Node - Placeholder"""

from ..state import AgentState, IncidentStatus, IncidentSeverity


async def analyze_incident(state: AgentState) -> AgentState:
    """Analyze incident with LLM - TO BE IMPLEMENTED"""
    state.status = IncidentStatus.ANALYZING
    # TODO: Implement LLM analysis (Bedrock/SageMaker)
    state.root_cause_hypothesis = "Placeholder analysis"
    state.severity = IncidentSeverity.HIGH
    state.analysis_complete = True
    state.next_step = "match_runbooks"
    return state
