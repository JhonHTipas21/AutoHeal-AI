"""
AutoHeal AI - Shared Constants
==============================

Centralized configuration constants used across all services.
These values can be overridden via environment variables.
"""

from enum import Enum


class ServiceName(str, Enum):
    """Names of all AutoHeal microservices."""
    MONITORING = "monitoring"
    LOG_INTELLIGENCE = "log-intelligence"
    INCIDENT_MANAGER = "incident-manager"
    AUTOHEAL_AGENT = "autoheal-agent"
    K8S_EXECUTOR = "k8s-executor"
    AUDIT_SERVICE = "audit-service"


class Severity(str, Enum):
    """Incident severity levels following industry standards."""
    CRITICAL = "critical"  # Service completely down, major user impact
    HIGH = "high"          # Significant degradation, many users affected
    MEDIUM = "medium"      # Partial degradation, some users affected
    LOW = "low"            # Minor issue, minimal user impact
    INFO = "info"          # Informational only, no action needed


class IncidentStatus(str, Enum):
    """Lifecycle status of an incident."""
    DETECTED = "detected"           # Initial detection
    ANALYZING = "analyzing"         # Under analysis
    HEALING_PLANNED = "healing_planned"  # Healing action planned
    HEALING_IN_PROGRESS = "healing_in_progress"  # Action being executed
    HEALING_COMPLETED = "healing_completed"  # Action completed
    VERIFIED = "verified"           # Post-healing verification passed
    RESOLVED = "resolved"           # Incident fully resolved
    FAILED = "failed"               # Healing failed
    ESCALATED = "escalated"         # Escalated to human operator


class HealingAction(str, Enum):
    """Types of healing actions the system can execute."""
    ROLLBACK = "rollback"           # Rollback to previous version
    SCALE_UP = "scale_up"           # Increase replicas
    SCALE_DOWN = "scale_down"       # Decrease replicas
    RESTART_POD = "restart_pod"     # Restart specific pod
    RESTART_DEPLOYMENT = "restart_deployment"  # Restart entire deployment
    NO_ACTION = "no_action"         # No action required
    ESCALATE = "escalate"           # Escalate to human


class AnomalyType(str, Enum):
    """Types of anomalies detected by the monitoring service."""
    ERROR_RATE_SPIKE = "error_rate_spike"
    LATENCY_SPIKE = "latency_spike"
    CPU_OVERLOAD = "cpu_overload"
    MEMORY_OVERLOAD = "memory_overload"
    POD_CRASH_LOOP = "pod_crash_loop"
    DEPLOYMENT_FAILURE = "deployment_failure"
    HEALTH_CHECK_FAILURE = "health_check_failure"


class LogErrorType(str, Enum):
    """Types of errors identified in logs."""
    NULL_POINTER = "null_pointer"
    OUT_OF_MEMORY = "out_of_memory"
    CONNECTION_REFUSED = "connection_refused"
    TIMEOUT = "timeout"
    AUTHENTICATION_FAILURE = "authentication_failure"
    DATABASE_ERROR = "database_error"
    CONFIGURATION_ERROR = "configuration_error"
    DEPENDENCY_FAILURE = "dependency_failure"
    UNKNOWN = "unknown"


# Default threshold values
class Thresholds:
    """Default threshold values for anomaly detection."""
    ERROR_RATE_PERCENT = 5.0        # 5% error rate triggers alert
    LATENCY_P99_MS = 1000           # 1 second P99 latency
    LATENCY_P95_MS = 500            # 500ms P95 latency
    CPU_PERCENT = 80                # 80% CPU usage
    MEMORY_PERCENT = 85             # 85% memory usage
    POD_RESTART_COUNT = 3           # 3 restarts in window
    

# Cooldown and timing constants
class Timing:
    """Timing constants for system behavior."""
    COOLDOWN_SECONDS = 300          # 5 minutes between healing attempts
    POLLING_INTERVAL_SECONDS = 15   # Metric polling interval
    VERIFICATION_DELAY_SECONDS = 60 # Wait before verifying healing
    VERIFICATION_TIMEOUT_SECONDS = 300  # Max wait for verification
    INCIDENT_TIMEOUT_SECONDS = 1800  # 30 minutes max incident duration


# HTTP status code classifications
HTTP_ERROR_CODES = range(500, 600)  # 5xx server errors
HTTP_CLIENT_ERROR_CODES = range(400, 500)  # 4xx client errors

# Service port mappings
SERVICE_PORTS = {
    ServiceName.MONITORING: 8000,
    ServiceName.LOG_INTELLIGENCE: 8001,
    ServiceName.INCIDENT_MANAGER: 8002,
    ServiceName.AUTOHEAL_AGENT: 8003,
    ServiceName.K8S_EXECUTOR: 8004,
    ServiceName.AUDIT_SERVICE: 8005,
}
