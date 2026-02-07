"""
AutoHeal AI - Audit Service Configuration
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""
    
    service_name: str = Field(default="audit-service")
    service_version: str = Field(default="0.1.0")
    
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8005)
    debug: bool = Field(default=False)
    
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=True)
    
    # Retention
    max_records: int = Field(default=10000, description="Max records to keep in memory")
    retention_days: int = Field(default=30, description="Days to retain audit records")
    
    class Config:
        env_prefix = ""
        case_sensitive = False
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
