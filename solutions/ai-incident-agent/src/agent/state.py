"""
Agent State Model for AI Incident Intelligence Agent

This module defines the state that flows through the LangGraph workflow.
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Optional, Sequence

from langchain_core.messages import BaseMessage
from pydantic import BaseModel, Field


class IncidentSeverity(str, Enum):
    """Incident severity levels"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class IncidentStatus(str, Enum):
    """Incident workflow status"""

    RECEIVED = "received"
    VALIDATING = "validating"
    GATHERING_CONTEXT = "gathering_context"
    ANALYZING = "analyzing"
    MATCHING_RUNBOOKS = "matching_runbooks"
    ENRICHING = "enriching"
    NOTIFYING = "notifying"
    AWAITING_FEEDBACK = "awaiting_feedback"
    RESOLVED = "resolved"
    FAILED = "failed"


class LogEntry(BaseModel):
    """Single log entry"""

    timestamp: datetime
    message: str
    level: str
    log_stream: str
    log_group: str


class MetricDataPoint(BaseModel):
    """Single metric data point"""

    timestamp: datetime
    value: float
    unit: str


class Metric(BaseModel):
    """Metric with multiple data points"""

    name: str
    namespace: str
    dimensions: dict[str, str]
    datapoints: list[MetricDataPoint]


class TraceSegment(BaseModel):
    """X-Ray trace segment"""

    trace_id: str
    segment_id: str
    start_time: datetime
    end_time: datetime
    http_status: Optional[int] = None
    error: bool = False
    fault: bool = False
    exception: Optional[dict[str, Any]] = None


class SimilarIncident(BaseModel):
    """Previously resolved similar incident"""

    incident_id: str
    similarity_score: float
    resource_type: str
    alert_type: str
    root_cause: str
    resolution: str
    resolved_at: datetime
    mttr_seconds: int


class Runbook(BaseModel):
    """Matched runbook"""

    runbook_id: str
    title: str
    s3_path: str
    match_score: float
    resource_types: list[str]
    alert_types: list[str]
    effectiveness_score: float


class AgentState(BaseModel):
    """
    State that flows through the LangGraph workflow.

    This is the complete state of an incident as it moves through
    the agent's processing pipeline.
    """

    # ========================================================================
    # Input - Alert Information
    # ========================================================================

    incident_id: str = Field(description="Unique incident identifier")
    alert_id: str = Field(description="Original alert/alarm identifier")
    alert_source: str = Field(description="Source system: cloudwatch, eventbridge, etc.")
    alert_type: str = Field(description="Type of alert: CPUUtilization, ErrorRate, etc.")
    alert_data: dict[str, Any] = Field(description="Raw alert payload")

    resource_type: str = Field(description="AWS resource type: eks, rds, ec2, lambda, etc.")
    resource_id: str = Field(description="Resource identifier: cluster name, instance ID, etc.")
    resource_region: str = Field(description="AWS region")

    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Alert timestamp")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Incident created")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last updated")

    # ========================================================================
    # Workflow State
    # ========================================================================

    status: IncidentStatus = Field(
        default=IncidentStatus.RECEIVED, description="Current workflow status"
    )
    next_step: str = Field(default="validate_alert", description="Next workflow node")

    error_message: Optional[str] = Field(
        default=None, description="Error if workflow failed"
    )

    # ========================================================================
    # Context Gathering
    # ========================================================================

    logs: list[LogEntry] = Field(default_factory=list, description="Collected log entries")
    metrics: list[Metric] = Field(default_factory=list, description="Collected metrics")
    traces: list[TraceSegment] = Field(default_factory=list, description="X-Ray trace segments")

    similar_incidents: list[SimilarIncident] = Field(
        default_factory=list, description="Similar past incidents"
    )

    resource_metadata: dict[str, Any] = Field(
        default_factory=dict, description="AWS resource metadata"
    )

    context_gathering_complete: bool = Field(
        default=False, description="Context gathering finished"
    )
    context_gathering_errors: list[str] = Field(
        default_factory=list, description="Errors during context gathering"
    )

    # ========================================================================
    # AI Analysis
    # ========================================================================

    root_cause_hypothesis: Optional[str] = Field(
        default=None, description="LLM-generated root cause hypothesis"
    )

    severity: Optional[IncidentSeverity] = Field(
        default=None, description="AI-assessed severity"
    )

    impact_assessment: Optional[str] = Field(
        default=None, description="Impact assessment (which users/services affected)"
    )

    affected_resources: list[str] = Field(
        default_factory=list, description="List of affected resource IDs"
    )

    analysis_confidence: float = Field(
        default=0.0, description="LLM confidence in analysis (0.0-1.0)"
    )

    analysis_complete: bool = Field(default=False, description="Analysis finished")

    # ========================================================================
    # Runbook Matching
    # ========================================================================

    matched_runbooks: list[Runbook] = Field(
        default_factory=list, description="Matched runbooks"
    )

    runbook_matching_complete: bool = Field(
        default=False, description="Runbook matching finished"
    )

    # ========================================================================
    # Recommendations & Actions
    # ========================================================================

    recommended_actions: list[str] = Field(
        default_factory=list, description="Immediate recommended actions"
    )

    escalation_needed: bool = Field(
        default=False, description="Should this be escalated?"
    )

    escalation_reason: Optional[str] = Field(
        default=None, description="Why escalation is needed"
    )

    # ========================================================================
    # Notification
    # ========================================================================

    notification_channels: list[str] = Field(
        default_factory=list, description="Channels to notify: slack, pagerduty, teams"
    )

    notification_sent: bool = Field(default=False, description="Notification delivered")

    slack_thread_ts: Optional[str] = Field(
        default=None, description="Slack message timestamp for threading"
    )

    pagerduty_incident_key: Optional[str] = Field(
        default=None, description="PagerDuty incident key"
    )

    # ========================================================================
    # Feedback & Learning
    # ========================================================================

    assigned_engineer: Optional[str] = Field(
        default=None, description="Engineer who acknowledged"
    )

    acknowledged_at: Optional[datetime] = Field(
        default=None, description="When incident was acknowledged"
    )

    engineer_feedback: dict[str, Any] = Field(
        default_factory=dict,
        description="Feedback from engineer (analysis helpful, actual root cause, etc.)",
    )

    resolved_at: Optional[datetime] = Field(default=None, description="Resolution timestamp")

    resolution_summary: Optional[str] = Field(
        default=None, description="How incident was resolved"
    )

    actual_root_cause: Optional[str] = Field(
        default=None, description="Actual root cause (from engineer feedback)"
    )

    mttr_seconds: Optional[int] = Field(
        default=None, description="Mean Time To Resolution in seconds"
    )

    # ========================================================================
    # Agent Internals (LangGraph)
    # ========================================================================

    messages: Annotated[Sequence[BaseMessage], "Agent reasoning trace"] = Field(
        default_factory=list, description="LLM conversation history"
    )

    llm_calls: int = Field(default=0, description="Number of LLM calls made")

    total_tokens_used: int = Field(default=0, description="Total tokens consumed")

    processing_time_seconds: float = Field(
        default=0.0, description="Total processing time"
    )

    # ========================================================================
    # Metadata & Tags
    # ========================================================================

    tags: dict[str, str] = Field(
        default_factory=dict, description="Custom tags for categorization"
    )

    environment: str = Field(default="production", description="Environment: dev, staging, prod")

    class Config:
        """Pydantic configuration"""

        arbitrary_types_allowed = True
        json_encoders = {datetime: lambda v: v.isoformat()}

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for storage"""
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentState":
        """Create state from dictionary"""
        return cls(**data)

    def calculate_mttr(self) -> Optional[int]:
        """Calculate MTTR if incident is resolved"""
        if self.resolved_at and self.created_at:
            delta = self.resolved_at - self.created_at
            return int(delta.total_seconds())
        return None

    def is_high_priority(self) -> bool:
        """Check if this is a high-priority incident"""
        if self.severity in [IncidentSeverity.CRITICAL, IncidentSeverity.HIGH]:
            return True
        if self.escalation_needed:
            return True
        return False

    def should_use_fast_llm(self) -> bool:
        """Determine if we should use the faster, cheaper LLM"""
        # Use fast LLM for low-severity, non-production incidents
        if self.severity in [IncidentSeverity.LOW, IncidentSeverity.INFO]:
            return True
        if self.environment != "production":
            return True
        return False
