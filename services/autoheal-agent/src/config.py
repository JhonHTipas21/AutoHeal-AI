"""
AutoHeal AI - AutoHeal Agent Configuration
============================================
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from enum import Enum


class HealingMode(str, Enum):
    """Healing operation modes."""
    AUTO = "auto"           # Fully automatic healing
    SEMI_AUTO = "semi_auto" # Generate plan, require approval
    MANUAL = "manual"       # Only suggest, don't execute


class Settings(BaseSettings):
    """Application settings."""
    
    service_name: str = Field(default="autoheal-agent")
    service_version: str = Field(default="0.1.0")
    
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8003)
    debug: bool = Field(default=False)
    
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=True)
    
    # Downstream services
    k8s_executor_url: str = Field(
        default="http://k8s-executor:8004",
        description="URL of the Kubernetes executor"
    )
    audit_service_url: str = Field(
        default="http://audit-service:8005",
        description="URL of the Audit Service"
    )
    incident_manager_url: str = Field(
        default="http://incident-manager:8002",
        description="URL of the Incident Manager"
    )
    
    # OODA Loop settings
    healing_mode: HealingMode = Field(
        default=HealingMode.AUTO,
        description="Healing operation mode"
    )
    max_healing_attempts: int = Field(
        default=3,
        description="Maximum healing attempts per incident"
    )
    healing_timeout_seconds: int = Field(
        default=300,
        description="Timeout for healing operations"
    )
    
    # SLM settings for decision making
    slm_provider: str = Field(
        default="mock",
        description="SLM provider for reasoning"
    )
    slm_temperature: float = Field(
        default=0.3,
        description="SLM temperature for reasoning"
    )
    
    # Safety limits
    max_concurrent_healings: int = Field(
        default=3,
        description="Maximum concurrent healing operations"
    )
    cooldown_minutes: int = Field(
        default=10,
        description="Cooldown between healing attempts for same service"
    )
    
    class Config:
        env_prefix = ""
        case_sensitive = False
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
