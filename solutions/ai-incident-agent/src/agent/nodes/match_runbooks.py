"""Runbook Matching Node - Placeholder"""

from ..state import AgentState


async def match_runbooks(state: AgentState) -> AgentState:
    """Match incident to runbooks - TO BE IMPLEMENTED"""
    # TODO: Implement vector search in OpenSearch
    state.runbook_matching_complete = True
    state.next_step = "enrich_notification"
    return state
