"""
Alert Validation Node

Validates incoming alerts and checks for duplicates.
"""

import hashlib
import structlog
from datetime import datetime, timedelta

from ..state import AgentState, IncidentStatus
from langchain_core.messages import AIMessage


logger = structlog.get_logger(__name__)


async def validate_alert(state: AgentState) -> AgentState:
    """
    Validate incoming alert and check for duplicates.

    This node:
    1. Validates alert data format
    2. Checks for required fields
    3. Deduplicates against recent incidents
    4. Updates state with validation results

    Args:
        state: Current agent state

    Returns:
        Updated agent state
    """

    logger.info(
        "validating_alert",
        incident_id=state.incident_id,
        alert_id=state.alert_id,
        resource_type=state.resource_type,
    )

    state.status = IncidentStatus.VALIDATING

    # Validate required fields
    validation_errors = []

    if not state.alert_id:
        validation_errors.append("Missing alert_id")

    if not state.resource_type or state.resource_type == "unknown":
        validation_errors.append("Could not determine resource_type")

    if not state.resource_id or state.resource_id == "unknown":
        validation_errors.append("Could not determine resource_id")

    if not state.alert_data:
        validation_errors.append("Empty alert_data")

    if validation_errors:
        error_msg = f"Alert validation failed: {', '.join(validation_errors)}"
        logger.warning(
            "alert_validation_failed",
            incident_id=state.incident_id,
            errors=validation_errors,
        )
        state.error_message = error_msg
        state.status = IncidentStatus.FAILED
        state.messages.append(
            AIMessage(content=f"Validation failed: {error_msg}")
        )
        return state

    # Check for duplicate alerts
    is_duplicate = await _check_duplicate(state)

    if is_duplicate:
        logger.info(
            "duplicate_alert_detected",
            incident_id=state.incident_id,
            alert_id=state.alert_id,
        )
        state.error_message = "Duplicate alert - already processing"
        state.status = IncidentStatus.FAILED
        state.messages.append(
            AIMessage(content="Alert is a duplicate of existing incident")
        )
        return state

    # Validation passed
    logger.info(
        "alert_validated",
        incident_id=state.incident_id,
        alert_id=state.alert_id,
        resource=f"{state.resource_type}/{state.resource_id}",
    )

    state.messages.append(
        AIMessage(
            content=f"Alert validated successfully: {state.alert_type} "
            f"for {state.resource_type}/{state.resource_id}"
        )
    )

    state.next_step = "gather_context"
    return state


async def _check_duplicate(state: AgentState) -> bool:
    """
    Check if this alert is a duplicate of a recent incident.

    Deduplication logic:
    - Generate alert signature (hash of key fields)
    - Check DynamoDB for incidents with same signature in last 5 minutes
    - If found, mark as duplicate

    Args:
        state: Current agent state

    Returns:
        True if duplicate, False otherwise
    """

    # Generate alert signature
    signature_data = (
        f"{state.alert_id}:"
        f"{state.resource_type}:"
        f"{state.resource_id}:"
        f"{state.alert_type}"
    )
    signature = hashlib.sha256(signature_data.encode()).hexdigest()[:16]

    # TODO: Implement DynamoDB check
    # For now, this is a placeholder
    # In production, query DynamoDB incident_state table for:
    #   - Same signature
    #   - created_at within last 5 minutes (configurable)
    #   - Status not in [RESOLVED, FAILED]

    logger.debug(
        "duplicate_check",
        incident_id=state.incident_id,
        signature=signature,
    )

    # Example implementation:
    # from src.integrations.aws import dynamodb_client
    #
    # dedup_window = timedelta(minutes=5)
    # cutoff_time = datetime.utcnow() - dedup_window
    #
    # response = await dynamodb_client.query(
    #     TableName=os.getenv("DYNAMODB_INCIDENT_STATE_TABLE"),
    #     IndexName="signature-created_at-index",
    #     KeyConditionExpression="signature = :sig AND created_at > :cutoff",
    #     ExpressionAttributeValues={
    #         ":sig": {"S": signature},
    #         ":cutoff": {"S": cutoff_time.isoformat()}
    #     }
    # )
    #
    # if response['Items']:
    #     return True  # Duplicate found

    return False  # No duplicate found (for now)
