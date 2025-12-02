"""Decision Nodes for Workflow Routing"""

from typing import Literal
from ..state import AgentState, IncidentSeverity


def should_escalate(state: AgentState) -> Literal["escalate", "proceed"]:
    """
    Decide if incident should be escalated.

    Escalation criteria:
    - Severity is CRITICAL
    - No matching runbook found
    - Resource is in production
    - Similar incident required escalation before
    """

    if state.severity == IncidentSeverity.CRITICAL:
        state.escalation_needed = True
        state.escalation_reason = "Critical severity"
        return "escalate"

    if not state.matched_runbooks and state.severity == IncidentSeverity.HIGH:
        state.escalation_needed = True
        state.escalation_reason = "No runbook found for high-severity incident"
        return "escalate"

    return "proceed"
