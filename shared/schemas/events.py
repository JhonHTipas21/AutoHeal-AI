"""
AutoHeal AI - Event Schemas
===========================

Pydantic models for events exchanged between services.
These schemas define the contract for inter-service communication.
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from enum import Enum

from shared.constants import Severity, AnomalyType, LogErrorType, IncidentStatus


class BaseEvent(BaseModel):
    """Base class for all events in the system."""
    
    event_id: str = Field(
        ...,
        description="Unique identifier for this event"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the event was generated"
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Correlation ID for distributed tracing"
    )
    source_service: str = Field(
        ...,
        description="Name of the service that generated this event"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AnomalyEvent(BaseEvent):
    """
    Event emitted by the Monitoring Service when an anomaly is detected.
    
    This is the primary trigger for the incident detection flow.
    Contains metric data and threshold violation details.
    """
    
    anomaly_type: AnomalyType = Field(
        ...,
        description="Type of anomaly detected"
    )
    severity: Severity = Field(
        ...,
        description="Assessed severity of the anomaly"
    )
    target_service: str = Field(
        ...,
        description="Name of the affected service/deployment"
    )
    target_namespace: str = Field(
        default="default",
        description="Kubernetes namespace of the affected service"
    )
    metric_name: str = Field(
        ...,
        description="Name of the metric that triggered the anomaly"
    )
    current_value: float = Field(
        ...,
        description="Current value of the metric"
    )
    threshold_value: float = Field(
        ...,
        description="Threshold that was violated"
    )
    threshold_direction: str = Field(
        default="above",
        description="Whether the value exceeded threshold 'above' or fell 'below'"
    )
    metric_window_seconds: int = Field(
        default=60,
        description="Time window over which the metric was evaluated"
    )
    additional_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context data for the anomaly"
    )


class LogAnalysisEvent(BaseEvent):
    """
    Event emitted by the Log Intelligence Service after analyzing logs.
    
    Contains the SLM's analysis of log entries including error classification,
    probable root cause, and any commit correlations.
    """
    
    target_service: str = Field(
        ...,
        description="Name of the service whose logs were analyzed"
    )
    target_namespace: str = Field(
        default="default",
        description="Kubernetes namespace"
    )
    error_type: LogErrorType = Field(
        ...,
        description="Classified type of error"
    )
    error_message: str = Field(
        ...,
        description="Original error message from logs"
    )
    probable_root_cause: str = Field(
        ...,
        description="SLM-inferred probable root cause"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the root cause analysis (0-1)"
    )
    related_commit: Optional[str] = Field(
        None,
        description="Git commit SHA if correlated with recent deployment"
    )
    related_deployment: Optional[str] = Field(
        None,
        description="Deployment version if identified"
    )
    log_snippet: str = Field(
        ...,
        description="Relevant log excerpt"
    )
    log_count: int = Field(
        default=1,
        description="Number of similar log entries in the analysis window"
    )
    first_seen: datetime = Field(
        ...,
        description="When the error was first observed"
    )
    last_seen: datetime = Field(
        ...,
        description="When the error was last observed"
    )


class IncidentEvent(BaseEvent):
    """
    Event representing a correlated incident created by the Incident Manager.
    
    Combines anomaly events and log analysis into a single incident
    with assessed severity and healing eligibility.
    """
    
    incident_id: str = Field(
        ...,
        description="Unique incident identifier"
    )
    status: IncidentStatus = Field(
        default=IncidentStatus.DETECTED,
        description="Current status of the incident"
    )
    severity: Severity = Field(
        ...,
        description="Overall assessed severity"
    )
    title: str = Field(
        ...,
        description="Human-readable incident title"
    )
    description: str = Field(
        ...,
        description="Detailed incident description"
    )
    target_service: str = Field(
        ...,
        description="Primary affected service"
    )
    target_namespace: str = Field(
        default="default",
        description="Kubernetes namespace"
    )
    related_anomalies: list[str] = Field(
        default_factory=list,
        description="List of anomaly event IDs that contributed"
    )
    related_log_analyses: list[str] = Field(
        default_factory=list,
        description="List of log analysis event IDs"
    )
    auto_heal_eligible: bool = Field(
        default=True,
        description="Whether automatic healing is allowed"
    )
    auto_heal_reason: Optional[str] = Field(
        None,
        description="Reason if auto-heal is not eligible"
    )
    recommended_action: Optional[str] = Field(
        None,
        description="Suggested healing action if determined"
    )


class HealingEvent(BaseEvent):
    """
    Event representing a healing action taken by the AutoHeal Agent.
    
    Documents the complete healing lifecycle including planning,
    execution, and verification results.
    """
    
    incident_id: str = Field(
        ...,
        description="Related incident ID"
    )
    healing_id: str = Field(
        ...,
        description="Unique healing action identifier"
    )
    action_type: str = Field(
        ...,
        description="Type of healing action (rollback, scale, restart)"
    )
    target_service: str = Field(
        ...,
        description="Service being healed"
    )
    target_namespace: str = Field(
        default="default",
        description="Kubernetes namespace"
    )
    
    # Planning phase
    reasoning: str = Field(
        ...,
        description="Agent's reasoning for choosing this action"
    )
    expected_outcome: str = Field(
        ...,
        description="Expected result of the healing action"
    )
    risk_assessment: str = Field(
        ...,
        description="Assessment of risks involved"
    )
    
    # Execution phase
    executed_at: Optional[datetime] = Field(
        None,
        description="When the action was executed"
    )
    execution_details: dict[str, Any] = Field(
        default_factory=dict,
        description="Details of the execution (commands, targets, etc.)"
    )
    
    # Verification phase
    verified_at: Optional[datetime] = Field(
        None,
        description="When verification was completed"
    )
    verification_result: Optional[str] = Field(
        None,
        description="Result of post-healing verification"
    )
    success: Optional[bool] = Field(
        None,
        description="Whether the healing was successful"
    )
    
    # Metrics
    duration_seconds: Optional[float] = Field(
        None,
        description="Total duration from start to verification"
    )
