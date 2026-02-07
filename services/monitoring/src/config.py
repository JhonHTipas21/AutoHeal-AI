"""
AutoHeal AI - Monitoring Service Configuration
===============================================

Centralized configuration using Pydantic Settings.
All configuration is loaded from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All settings have defaults suitable for local development.
    In production, these should be overridden via environment variables
    or a configuration management system.
    """
    
    # Service identification
    service_name: str = Field(
        default="monitoring",
        description="Name of this service for logging and tracing"
    )
    service_version: str = Field(
        default="0.1.0",
        description="Semantic version of the service"
    )
    
    # Server configuration
    host: str = Field(default="0.0.0.0", description="Host to bind to")
    port: int = Field(default=8000, description="Port to listen on")
    debug: bool = Field(default=False, description="Enable debug mode")
    
    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    log_json: bool = Field(
        default=True,
        description="Output logs as JSON"
    )
    
    # Prometheus integration
    prometheus_url: str = Field(
        default="http://prometheus:9090",
        description="URL of the Prometheus server"
    )
    prometheus_timeout_seconds: float = Field(
        default=10.0,
        description="Timeout for Prometheus queries"
    )
    
    # Downstream services
    incident_manager_url: str = Field(
        default="http://incident-manager:8002",
        description="URL of the Incident Manager service"
    )
    audit_service_url: str = Field(
        default="http://audit-service:8005",
        description="URL of the Audit Service"
    )
    
    # Polling configuration
    polling_interval_seconds: int = Field(
        default=15,
        description="How often to poll for metrics"
    )
    polling_enabled: bool = Field(
        default=True,
        description="Enable automatic metric polling"
    )
    
    # Anomaly detection thresholds
    anomaly_threshold_error_rate: float = Field(
        default=0.05,
        description="Error rate threshold (0.05 = 5%)"
    )
    anomaly_threshold_latency_p99_ms: int = Field(
        default=1000,
        description="P99 latency threshold in milliseconds"
    )
    anomaly_threshold_latency_p95_ms: int = Field(
        default=500,
        description="P95 latency threshold in milliseconds"
    )
    anomaly_threshold_cpu_percent: int = Field(
        default=80,
        description="CPU usage threshold percentage"
    )
    anomaly_threshold_memory_percent: int = Field(
        default=85,
        description="Memory usage threshold percentage"
    )
    
    # Alert configuration
    alert_cooldown_seconds: int = Field(
        default=60,
        description="Minimum time between duplicate alerts"
    )
    alert_batch_size: int = Field(
        default=10,
        description="Maximum alerts to send in a batch"
    )
    
    class Config:
        env_prefix = ""  # No prefix for environment variables
        case_sensitive = False
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    The @lru_cache decorator ensures settings are loaded only once
    and reused across the application lifetime.
    
    Returns:
        Configured Settings instance
    """
    return Settings()
