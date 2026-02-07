"""
AutoHeal AI - Log Intelligence Service Configuration
=====================================================

Centralized configuration using Pydantic Settings.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from enum import Enum


class SLMProvider(str, Enum):
    """Available SLM providers for log analysis."""
    MOCK = "mock"           # Mock responses for development/testing
    TINYLLAMA = "tinyllama" # TinyLlama model (requires transformers)
    OLLAMA = "ollama"       # Ollama local inference


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    
    # Service identification
    service_name: str = Field(
        default="log-intelligence",
        description="Name of this service"
    )
    service_version: str = Field(
        default="0.1.0",
        description="Semantic version"
    )
    
    # Server configuration
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8001)
    debug: bool = Field(default=False)
    
    # Logging
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=True)
    
    # Loki integration
    loki_url: str = Field(
        default="http://loki:3100",
        description="URL of the Loki server"
    )
    loki_timeout_seconds: float = Field(
        default=10.0,
        description="Timeout for Loki queries"
    )
    
    # Downstream services
    incident_manager_url: str = Field(
        default="http://incident-manager:8002",
        description="URL of the Incident Manager"
    )
    audit_service_url: str = Field(
        default="http://audit-service:8005",
        description="URL of the Audit Service"
    )
    
    # SLM Configuration
    slm_provider: SLMProvider = Field(
        default=SLMProvider.MOCK,
        description="SLM provider to use (mock, tinyllama, ollama)"
    )
    slm_model_name: str = Field(
        default="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        description="HuggingFace model name for SLM"
    )
    slm_ollama_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API URL"
    )
    slm_max_tokens: int = Field(
        default=512,
        description="Maximum tokens for SLM response"
    )
    slm_temperature: float = Field(
        default=0.3,
        description="Temperature for SLM generation"
    )
    
    # Log analysis settings
    log_batch_size: int = Field(
        default=100,
        description="Number of logs to analyze in a batch"
    )
    log_retention_hours: int = Field(
        default=24,
        description="Hours of logs to consider for analysis"
    )
    error_correlation_window_minutes: int = Field(
        default=30,
        description="Time window for correlating errors with commits"
    )
    
    # Git/Commit tracking
    git_repo_url: str = Field(
        default="",
        description="URL of the Git repository for commit correlation"
    )
    
    class Config:
        env_prefix = ""
        case_sensitive = False
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
