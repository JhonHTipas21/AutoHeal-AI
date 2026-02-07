"""
AutoHeal AI - Incident Manager API Schemas
============================================
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class IncidentStatus(str, Enum):
    """Incident lifecycle status."""
    NEW = "new"
    ANALYZING = "analyzing"
    HEALING = "healing"
    AWAITING_APPROVAL = "awaiting_approval"
    RESOLVED = "resolved"
    FAILED = "failed"


class IncidentSeverity(str, Enum):
    """Incident severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EventType(str, Enum):
    """Types of events that can create/update incidents."""
    ANOMALY = "anomaly"
    LOG_ANALYSIS = "log_analysis"
    MANUAL = "manual"


class AnomalyEventInput(BaseModel):
    """Incoming anomaly event from monitoring service."""
    
    event_id: str = Field(..., description="Unique event ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_service: str = Field(default="monitoring")
    anomaly_type: str = Field(..., description="Type of anomaly")
    severity: str = Field(default="medium")
    target_service: str = Field(..., description="Affected service")
    target_namespace: str = Field(default="default")
    metric_name: str = Field(...)
    current_value: float = Field(...)
    threshold_value: float = Field(...)
    threshold_direction: str = Field(default="above")
    metric_window_seconds: int = Field(default=300)
    additional_context: dict = Field(default_factory=dict)
    correlation_id: Optional[str] = None


class LogAnalysisEventInput(BaseModel):
    """Incoming log analysis event."""
    
    event_id: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_service: str = Field(default="log-intelligence")
    event_type: str = Field(default="log_analysis")
    service_name: str = Field(...)
    namespace: str = Field(default="default")
    error_category: str = Field(...)
    error_count: int = Field(default=1)
    severity: str = Field(default="medium")
    root_cause: str = Field(...)
    confidence: float = Field(ge=0, le=1)
    sample_message: str = Field(...)
    recommended_actions: list[str] = Field(default_factory=list)
    first_occurrence: datetime = Field(default_factory=datetime.utcnow)


class Incident(BaseModel):
    """Full incident model."""
    
    incident_id: str = Field(...)
    title: str = Field(...)
    description: str = Field(...)
    status: IncidentStatus = Field(default=IncidentStatus.NEW)
    severity: IncidentSeverity = Field(...)
    
    # Affected service
    target_service: str = Field(...)
    target_namespace: str = Field(default="default")
    
    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    
    # Related events
    event_ids: list[str] = Field(default_factory=list)
    event_count: int = Field(default=1)
    
    # Analysis
    root_cause: Optional[str] = None
    confidence: Optional[float] = None
    
    # Healing
    healing_plan_id: Optional[str] = None
    healing_actions: list[str] = Field(default_factory=list)
    healing_result: Optional[str] = None


class IncidentListResponse(BaseModel):
    """Response for listing incidents."""
    
    incidents: list[Incident]
    total: int
    page: int = 1
    page_size: int = 20


class TriggerHealingRequest(BaseModel):
    """Request to trigger healing for an incident."""
    
    incident_id: str = Field(...)
    approved_by: Optional[str] = None
    force: bool = Field(default=False)
