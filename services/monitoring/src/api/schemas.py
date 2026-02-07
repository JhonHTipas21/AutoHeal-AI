"""
AutoHeal AI - Monitoring Service API Schemas
=============================================

Pydantic models for API request/response validation.
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class MetricType(str, Enum):
    """Types of metrics collected by the monitoring service."""
    ERROR_RATE = "error_rate"
    LATENCY_P50 = "latency_p50"
    LATENCY_P95 = "latency_p95"
    LATENCY_P99 = "latency_p99"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    REQUEST_COUNT = "request_count"
    POD_RESTART_COUNT = "pod_restart_count"


class MetricValue(BaseModel):
    """A single metric value with metadata."""
    
    metric_type: MetricType = Field(..., description="Type of metric")
    value: float = Field(..., description="Metric value")
    labels: dict[str, str] = Field(
        default_factory=dict,
        description="Prometheus labels (service, namespace, etc.)"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the metric was collected"
    )


class ServiceMetrics(BaseModel):
    """Collection of metrics for a single service."""
    
    service_name: str = Field(..., description="Name of the service")
    namespace: str = Field(default="default", description="Kubernetes namespace")
    metrics: list[MetricValue] = Field(
        default_factory=list,
        description="Collected metrics"
    )
    collected_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Collection timestamp"
    )


class AnomalyResponse(BaseModel):
    """Response model for detected anomalies."""
    
    anomaly_id: str = Field(..., description="Unique anomaly identifier")
    anomaly_type: str = Field(..., description="Type of anomaly")
    severity: str = Field(..., description="Severity level")
    service_name: str = Field(..., description="Affected service")
    namespace: str = Field(default="default", description="Kubernetes namespace")
    metric_name: str = Field(..., description="Metric that triggered anomaly")
    current_value: float = Field(..., description="Current metric value")
    threshold_value: float = Field(..., description="Threshold that was exceeded")
    detected_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Detection timestamp"
    )
    message: str = Field(..., description="Human-readable anomaly description")


class ThresholdConfig(BaseModel):
    """Configuration for anomaly detection thresholds."""
    
    error_rate: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="Error rate threshold (0.05 = 5%)"
    )
    latency_p99_ms: int = Field(
        default=1000,
        ge=0,
        description="P99 latency threshold in milliseconds"
    )
    latency_p95_ms: int = Field(
        default=500,
        ge=0,
        description="P95 latency threshold in milliseconds"
    )
    cpu_percent: int = Field(
        default=80,
        ge=0,
        le=100,
        description="CPU usage threshold percentage"
    )
    memory_percent: int = Field(
        default=85,
        ge=0,
        le=100,
        description="Memory usage threshold percentage"
    )


class ThresholdUpdateRequest(BaseModel):
    """Request to update anomaly detection thresholds."""
    
    thresholds: ThresholdConfig = Field(
        ...,
        description="New threshold configuration"
    )
    

class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    uptime_seconds: Optional[float] = Field(
        None,
        description="Service uptime in seconds"
    )
    prometheus_connected: bool = Field(
        default=False,
        description="Whether Prometheus is reachable"
    )


class MetricsQueryRequest(BaseModel):
    """Request to query metrics for a specific service."""
    
    service_name: str = Field(..., description="Service name to query")
    namespace: str = Field(default="default", description="Kubernetes namespace")
    metric_types: list[MetricType] = Field(
        default_factory=lambda: list(MetricType),
        description="Types of metrics to retrieve"
    )
    time_range_minutes: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Time range for metric query"
    )
