"""
AutoHeal AI - K8s Executor API Schemas
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class ActionType(str, Enum):
    RESTART_POD = "restart_pod"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    ROLLBACK = "rollback"
    INCREASE_RESOURCES = "increase_resources"
    DELETE_POD = "delete_pod"
    PATCH_DEPLOYMENT = "patch_deployment"


class ActionStatus(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecuteRequest(BaseModel):
    """Request to execute a K8s action."""
    action_id: str = Field(...)
    action_type: ActionType = Field(...)
    target: str = Field(..., description="namespace/resource format")
    parameters: dict[str, Any] = Field(default_factory=dict)


class ExecuteResponse(BaseModel):
    """Response from action execution."""
    action_id: str
    status: ActionStatus
    message: str
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    dry_run: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ActionHistory(BaseModel):
    """Historical action record."""
    action_id: str
    action_type: str
    target: str
    status: ActionStatus
    executed_at: datetime
    duration_ms: int
    error_message: Optional[str] = None
