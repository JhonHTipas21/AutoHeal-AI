"""
AutoHeal AI - Audit Service API Schemas
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class AuditEventType(str, Enum):
    INCIDENT_CREATED = "incident_created"
    INCIDENT_UPDATED = "incident_updated"
    INCIDENT_RESOLVED = "incident_resolved"
    HEALING_STARTED = "healing_started"
    HEALING_COMPLETED = "healing_completed"
    HEALING_FAILED = "healing_failed"
    ACTION_EXECUTED = "action_executed"
    DECISION_MADE = "decision_made"


class AuditRecord(BaseModel):
    """An audit record for tracking decisions and actions."""
    
    record_id: str = Field(...)
    event_type: AuditEventType = Field(...)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Context
    service_name: str = Field(...)
    namespace: str = Field(default="default")
    incident_id: Optional[str] = None
    healing_id: Optional[str] = None
    
    # Details
    description: str = Field(...)
    reasoning: Optional[str] = None
    confidence: Optional[float] = None
    
    # Outcome
    success: Optional[bool] = None
    error_message: Optional[str] = None
    
    # Metadata
    correlation_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateAuditRecord(BaseModel):
    """Request to create an audit record."""
    event_type: AuditEventType = Field(...)
    service_name: str = Field(...)
    namespace: str = Field(default="default")
    incident_id: Optional[str] = None
    healing_id: Optional[str] = None
    description: str = Field(...)
    reasoning: Optional[str] = None
    confidence: Optional[float] = None
    success: Optional[bool] = None
    error_message: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditListResponse(BaseModel):
    """Response for listing audit records."""
    records: list[AuditRecord]
    total: int
    page: int = 1
    page_size: int = 50
