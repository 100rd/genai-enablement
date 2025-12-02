"""
LangGraph Workflow for AI Incident Intelligence Agent

This module defines the main agent workflow using LangGraph's state machine.
"""

import time
from typing import Literal

from langgraph.graph import END, StateGraph
from langchain_core.messages import HumanMessage, AIMessage

from .state import AgentState, IncidentStatus
from .nodes import (
    validate_alert,
    gather_context,
    analyze_incident,
    match_runbooks,
    should_escalate,
    enrich_notification,
    send_notifications,
)


def create_incident_workflow() -> StateGraph:
    """
    Create the LangGraph workflow for incident processing.

    Workflow Steps:
    1. validate_alert: Check alert format and deduplicate
    2. gather_context: Collect logs, metrics, traces, similar incidents
    3. analyze_incident: Use LLM to analyze root cause and impact
    4. match_runbooks: Find relevant runbooks
    5. should_escalate: Decide if escalation is needed
    6. enrich_notification: Create human-friendly summary
    7. send_notifications: Deliver to Slack/PagerDuty/Teams

    Returns:
        StateGraph: Compiled LangGraph workflow
    """

    # Create the state graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("validate_alert", validate_alert)
    workflow.add_node("gather_context", gather_context)
    workflow.add_node("analyze_incident", analyze_incident)
    workflow.add_node("match_runbooks", match_runbooks)
    workflow.add_node("enrich_notification", enrich_notification)
    workflow.add_node("send_notifications", send_notifications)

    # Set entry point
    workflow.set_entry_point("validate_alert")

    # Add edges (workflow transitions)
    workflow.add_conditional_edges(
        "validate_alert",
        _route_after_validation,
        {
            "gather_context": "gather_context",
            "end": END,
        },
    )

    workflow.add_edge("gather_context", "analyze_incident")
    workflow.add_edge("analyze_incident", "match_runbooks")

    workflow.add_conditional_edges(
        "match_runbooks",
        should_escalate,
        {
            "escalate": "enrich_notification",  # Even escalations get enrichment
            "proceed": "enrich_notification",
        },
    )

    workflow.add_edge("enrich_notification", "send_notifications")
    workflow.add_edge("send_notifications", END)

    return workflow.compile()


def _route_after_validation(state: AgentState) -> Literal["gather_context", "end"]:
    """
    Routing logic after alert validation.

    Args:
        state: Current agent state

    Returns:
        Next node to execute
    """
    if state.error_message:
        # Validation failed, end workflow
        return "end"

    # Validation passed, gather context
    return "gather_context"


async def process_alert(
    alert_data: dict,
    workflow: StateGraph,
) -> AgentState:
    """
    Process a single alert through the workflow.

    Args:
        alert_data: Raw alert payload from CloudWatch/EventBridge
        workflow: Compiled LangGraph workflow

    Returns:
        Final agent state after processing

    Example:
        >>> alert = {
        ...     "AlarmName": "eks-cluster-cpu-high",
        ...     "NewStateValue": "ALARM",
        ...     "StateChangeTime": "2025-12-02T10:30:00.000Z",
        ...     "Region": "us-east-1",
        ...     "Dimensions": [{"name": "ClusterName", "value": "my-cluster"}]
        ... }
        >>> state = await process_alert(alert, workflow)
        >>> print(f"Incident {state.incident_id} processed in {state.processing_time_seconds}s")
    """

    start_time = time.time()

    # Create initial state from alert
    initial_state = _create_initial_state(alert_data)

    # Run through workflow
    try:
        final_state = await workflow.ainvoke(initial_state)
        final_state.processing_time_seconds = time.time() - start_time
        final_state.status = IncidentStatus.AWAITING_FEEDBACK

    except Exception as e:
        # Workflow failed
        initial_state.status = IncidentStatus.FAILED
        initial_state.error_message = str(e)
        initial_state.processing_time_seconds = time.time() - start_time
        final_state = initial_state

    return final_state


def _create_initial_state(alert_data: dict) -> AgentState:
    """
    Create initial agent state from alert payload.

    Args:
        alert_data: Raw alert from CloudWatch/EventBridge

    Returns:
        Initial AgentState
    """

    from datetime import datetime
    import uuid

    # Extract common alert fields (adjust based on your alert format)
    incident_id = f"inc-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    alert_id = alert_data.get("AlarmName", alert_data.get("id", "unknown"))
    alert_source = alert_data.get("Source", "cloudwatch")

    # Determine resource type and ID from dimensions or alert name
    resource_type = _extract_resource_type(alert_data)
    resource_id = _extract_resource_id(alert_data)
    resource_region = alert_data.get("Region", "us-east-1")

    # Create initial state
    state = AgentState(
        incident_id=incident_id,
        alert_id=alert_id,
        alert_source=alert_source,
        alert_type=alert_data.get("AlarmName", ""),
        alert_data=alert_data,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_region=resource_region,
        timestamp=datetime.utcnow(),
        status=IncidentStatus.RECEIVED,
        messages=[
            HumanMessage(
                content=f"New alert received: {alert_id} for {resource_type}/{resource_id}"
            )
        ],
    )

    return state


def _extract_resource_type(alert_data: dict) -> str:
    """
    Extract AWS resource type from alert data.

    Tries to infer from:
    - Alarm name pattern (e.g., "eks-cluster-cpu" -> "eks")
    - Namespace (e.g., "AWS/EKS" -> "eks")
    - Dimensions

    Args:
        alert_data: Alert payload

    Returns:
        Resource type string (eks, rds, ec2, lambda, etc.)
    """

    # Try namespace first
    namespace = alert_data.get("Namespace", "")
    if namespace.startswith("AWS/"):
        return namespace.replace("AWS/", "").lower()

    # Try alarm name patterns
    alarm_name = alert_data.get("AlarmName", "").lower()
    for resource_type in ["eks", "rds", "ec2", "lambda", "dynamodb", "s3", "elb", "alb"]:
        if resource_type in alarm_name:
            return resource_type

    # Try dimensions
    dimensions = alert_data.get("Dimensions", [])
    for dim in dimensions:
        name = dim.get("name", "").lower()
        if "cluster" in name:
            return "eks"
        elif "dbinstance" in name:
            return "rds"
        elif "instance" in name:
            return "ec2"
        elif "function" in name:
            return "lambda"

    return "unknown"


def _extract_resource_id(alert_data: dict) -> str:
    """
    Extract resource identifier from alert data.

    Args:
        alert_data: Alert payload

    Returns:
        Resource ID (cluster name, instance ID, etc.)
    """

    # Try dimensions
    dimensions = alert_data.get("Dimensions", [])
    for dim in dimensions:
        value = dim.get("value", "")
        if value:
            return value

    # Fallback to alarm name
    return alert_data.get("AlarmName", "unknown")


# ============================================================================
# Workflow Statistics and Monitoring
# ============================================================================


def get_workflow_stats(state: AgentState) -> dict:
    """
    Get statistics about workflow execution.

    Args:
        state: Agent state after workflow completion

    Returns:
        Dict with workflow statistics
    """

    return {
        "incident_id": state.incident_id,
        "status": state.status.value,
        "processing_time_seconds": state.processing_time_seconds,
        "llm_calls": state.llm_calls,
        "total_tokens": state.total_tokens_used,
        "severity": state.severity.value if state.severity else None,
        "escalation_needed": state.escalation_needed,
        "logs_collected": len(state.logs),
        "metrics_collected": len(state.metrics),
        "traces_collected": len(state.traces),
        "similar_incidents_found": len(state.similar_incidents),
        "runbooks_matched": len(state.matched_runbooks),
        "notification_sent": state.notification_sent,
        "notification_channels": state.notification_channels,
        "errors": state.error_message,
    }


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    """
    Example: Run the workflow locally for testing
    """

    import asyncio

    # Example CloudWatch alarm payload
    example_alert = {
        "AlarmName": "eks-prod-cluster-cpu-high",
        "AlarmDescription": "EKS cluster CPU usage above 80%",
        "NewStateValue": "ALARM",
        "NewStateReason": "Threshold Crossed: 1 datapoint [85.0] was greater than threshold [80.0]",
        "StateChangeTime": "2025-12-02T10:30:00.000Z",
        "Region": "us-east-1",
        "Namespace": "AWS/EKS",
        "MetricName": "CPUUtilization",
        "Dimensions": [{"name": "ClusterName", "value": "prod-cluster"}],
        "Period": 300,
        "EvaluationPeriods": 1,
        "Threshold": 80.0,
    }

    async def main():
        # Create workflow
        workflow = create_incident_workflow()

        # Process alert
        print(f"Processing alert: {example_alert['AlarmName']}")
        final_state = await process_alert(example_alert, workflow)

        # Print results
        stats = get_workflow_stats(final_state)
        print(f"\nWorkflow completed:")
        print(f"  Incident ID: {stats['incident_id']}")
        print(f"  Status: {stats['status']}")
        print(f"  Processing time: {stats['processing_time_seconds']:.2f}s")
        print(f"  Severity: {stats['severity']}")
        print(f"  Escalation needed: {stats['escalation_needed']}")
        print(f"  Runbooks matched: {stats['runbooks_matched']}")
        print(f"  Notification sent: {stats['notification_sent']}")

        if final_state.root_cause_hypothesis:
            print(f"\nRoot Cause Hypothesis:")
            print(f"  {final_state.root_cause_hypothesis}")

        if final_state.recommended_actions:
            print(f"\nRecommended Actions:")
            for action in final_state.recommended_actions:
                print(f"  - {action}")

    asyncio.run(main())
