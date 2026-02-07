"""
AutoHeal AI - K8s Executor Configuration
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""
    
    service_name: str = Field(default="k8s-executor")
    service_version: str = Field(default="0.1.0")
    
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8004)
    debug: bool = Field(default=False)
    
    log_level: str = Field(default="INFO")
    log_json: bool = Field(default=True)
    
    # Kubernetes
    k8s_in_cluster: bool = Field(
        default=True,
        description="Use in-cluster config"
    )
    k8s_kubeconfig: str = Field(
        default="",
        description="Path to kubeconfig file"
    )
    k8s_namespace: str = Field(
        default="default",
        description="Default namespace"
    )
    
    # Safety limits
    dry_run: bool = Field(
        default=False,
        description="If true, only simulate actions"
    )
    max_pod_restarts: int = Field(
        default=5,
        description="Max pods to restart at once"
    )
    max_scale_increment: int = Field(
        default=5,
        description="Max replicas to add"
    )
    
    # Audit
    audit_service_url: str = Field(
        default="http://audit-service:8005"
    )
    
    class Config:
        env_prefix = ""
        case_sensitive = False
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
