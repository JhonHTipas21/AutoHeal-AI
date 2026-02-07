"""
AutoHeal AI - Incident Manager Configuration
==============================================
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""
    
    service_name: str = Field(default="incident-manager")
    service_version: str = Field(default="0.1.0")
    
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8002)
    debug: bool = Field(default=False)
    
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=True)
    
    # Downstream services
    autoheal_agent_url: str = Field(
        default="http://autoheal-agent:8003",
        description="URL of the AutoHeal Agent"
    )
    audit_service_url: str = Field(
        default="http://audit-service:8005",
        description="URL of the Audit Service"
    )
    
    # Incident settings
    incident_correlation_window_minutes: int = Field(
        default=15,
        description="Time window for correlating related events"
    )
    incident_auto_resolve_hours: int = Field(
        default=24,
        description="Hours before unresolved incidents auto-close"
    )
    healing_enabled: bool = Field(
        default=True,
        description="Enable automatic healing"
    )
    approval_required: bool = Field(
        default=False,
        description="Require manual approval for healing actions"
    )
    
    class Config:
        env_prefix = ""
        case_sensitive = False
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
