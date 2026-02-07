"""
AutoHeal AI - Log Intelligence API Schemas
============================================

Pydantic models for log analysis API.
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class LogLevel(str, Enum):
    """Standard log levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Categories of errors identified by the SLM."""
    NULL_POINTER = "null_pointer"
    OUT_OF_MEMORY = "out_of_memory"
    CONNECTION_ERROR = "connection_error"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATABASE = "database"
    CONFIGURATION = "configuration"
    DEPENDENCY = "dependency"
    VALIDATION = "validation"
    RATE_LIMIT = "rate_limit"
    UNKNOWN = "unknown"


class LogEntry(BaseModel):
    """A single log entry for analysis."""
    
    timestamp: datetime = Field(
        ...,
        description="When the log was generated"
    )
    service: str = Field(
        ...,
        description="Name of the service that generated the log"
    )
    namespace: str = Field(
        default="default",
        description="Kubernetes namespace"
    )
    level: LogLevel = Field(
        ...,
        description="Log level"
    )
    message: str = Field(
        ...,
        description="Log message content"
    )
    logger: Optional[str] = Field(
        None,
        description="Logger name/module"
    )
    trace_id: Optional[str] = Field(
        None,
        description="Distributed trace ID"
    )
    span_id: Optional[str] = Field(
        None,
        description="Span ID for tracing"
    )
    exception: Optional[str] = Field(
        None,
        description="Exception stack trace if present"
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured fields"
    )


class LogBatch(BaseModel):
    """Batch of log entries for analysis."""
    
    logs: list[LogEntry] = Field(
        ...,
        description="List of log entries"
    )
    source: str = Field(
        default="api",
        description="Source of the logs (api, loki, file)"
    )


class AnalysisRequest(BaseModel):
    """Request to analyze logs for a specific service."""
    
    service_name: str = Field(
        ...,
        description="Service to analyze logs for"
    )
    namespace: str = Field(
        default="default",
        description="Kubernetes namespace"
    )
    time_range_minutes: int = Field(
        default=30,
        ge=1,
        le=1440,
        description="Time range for log analysis"
    )
    include_info: bool = Field(
        default=False,
        description="Include INFO level logs"
    )
    max_logs: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum logs to analyze"
    )


class ErrorAnalysis(BaseModel):
    """Analysis result for a detected error."""
    
    error_id: str = Field(
        ...,
        description="Unique identifier for this error analysis"
    )
    category: ErrorCategory = Field(
        ...,
        description="Classified error category"
    )
    severity: str = Field(
        ...,
        description="Severity level (critical, high, medium, low)"
    )
    original_message: str = Field(
        ...,
        description="Original error message"
    )
    root_cause: str = Field(
        ...,
        description="Inferred probable root cause"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0-1)"
    )
    recommended_actions: list[str] = Field(
        default_factory=list,
        description="Suggested remediation actions"
    )
    related_commit: Optional[str] = Field(
        None,
        description="Correlated git commit SHA"
    )
    related_deployment: Optional[str] = Field(
        None,
        description="Related deployment version"
    )
    first_occurrence: datetime = Field(
        ...,
        description="First occurrence of this error"
    )
    occurrence_count: int = Field(
        default=1,
        description="Number of occurrences"
    )
    sample_logs: list[str] = Field(
        default_factory=list,
        description="Sample log messages"
    )


class AnalysisResponse(BaseModel):
    """Response from log analysis."""
    
    analysis_id: str = Field(
        ...,
        description="Unique analysis identifier"
    )
    service_name: str = Field(
        ...,
        description="Analyzed service"
    )
    namespace: str = Field(
        ...,
        description="Kubernetes namespace"
    )
    analyzed_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When analysis was performed"
    )
    total_logs_analyzed: int = Field(
        ...,
        description="Total logs processed"
    )
    error_count: int = Field(
        ...,
        description="Number of errors found"
    )
    errors: list[ErrorAnalysis] = Field(
        default_factory=list,
        description="Detailed error analyses"
    )
    summary: str = Field(
        ...,
        description="Human-readable analysis summary"
    )
    slm_provider: str = Field(
        ...,
        description="SLM provider used for analysis"
    )


class CommitInfo(BaseModel):
    """Information about a git commit."""
    
    sha: str = Field(..., description="Commit SHA")
    message: str = Field(..., description="Commit message")
    author: str = Field(..., description="Commit author")
    timestamp: datetime = Field(..., description="Commit timestamp")
    files_changed: list[str] = Field(
        default_factory=list,
        description="Files modified in commit"
    )


class CorrelationResult(BaseModel):
    """Result of commit-error correlation."""
    
    error_pattern: str = Field(
        ...,
        description="Error pattern being correlated"
    )
    correlated_commits: list[CommitInfo] = Field(
        default_factory=list,
        description="Commits that may be related"
    )
    correlation_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the correlation"
    )
    reasoning: str = Field(
        ...,
        description="Explanation of correlation"
    )
