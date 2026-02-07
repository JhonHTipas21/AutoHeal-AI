"""
AutoHeal AI - Structured Logging
================================

Provides consistent, structured JSON logging across all services.
Includes correlation ID propagation for distributed tracing.

Usage:
    from shared.utils.logging import get_logger, setup_logging
    
    setup_logging(service_name="monitoring", log_level="INFO")
    logger = get_logger(__name__)
    
    logger.info("Processing request", extra={"correlation_id": "abc123"})
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Optional
from contextvars import ContextVar

# Context variable for correlation ID propagation
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs as JSON.
    
    This enables easy parsing by log aggregation systems like Loki or ELK.
    Each log entry includes:
    - timestamp (ISO 8601 format with timezone)
    - level (log level name)
    - service (service name that generated the log)
    - logger (logger name, typically module path)
    - message (the log message)
    - correlation_id (for distributed tracing, if available)
    - Additional fields from the extra dict
    """
    
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string."""
        # Base log structure
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add correlation ID if present
        correlation_id = correlation_id_var.get()
        if correlation_id:
            log_entry["correlation_id"] = correlation_id
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add any extra fields (excluding standard LogRecord attributes)
        standard_attrs = {
            "name", "msg", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "pathname", "process", "processName", "relativeCreated",
            "stack_info", "exc_info", "exc_text", "thread", "threadName",
            "taskName", "message"
        }
        
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_entry[key] = value
        
        return json.dumps(log_entry, default=str)


class ContextualLogger(logging.LoggerAdapter):
    """
    Logger adapter that automatically includes context variables.
    
    Wraps a standard logger to automatically inject correlation IDs
    and other contextual information into log records.
    """
    
    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        """Process the logging call to add extra context."""
        extra = kwargs.get("extra", {})
        
        # Add correlation ID from context if not already present
        if "correlation_id" not in extra:
            correlation_id = correlation_id_var.get()
            if correlation_id:
                extra["correlation_id"] = correlation_id
        
        kwargs["extra"] = extra
        return msg, kwargs


# Service-specific loggers cache
_loggers: dict[str, ContextualLogger] = {}
_service_name: str = "autoheal"


def setup_logging(
    service_name: str,
    log_level: str = "INFO",
    json_output: bool = True
) -> None:
    """
    Configure logging for a service.
    
    Should be called once at service startup, typically in main.py.
    
    Args:
        service_name: Name of the service (e.g., "monitoring")
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: If True, output JSON format; otherwise use standard format
    
    Example:
        setup_logging(service_name="monitoring", log_level="INFO")
    """
    global _service_name
    _service_name = service_name
    
    # Get root logger and clear existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # Create handler based on format preference
    handler = logging.StreamHandler(sys.stdout)
    
    if json_output:
        handler.setFormatter(StructuredFormatter(service_name))
    else:
        # Human-readable format for local development
        handler.setFormatter(logging.Formatter(
            f"%(asctime)s | {service_name} | %(levelname)s | %(name)s | %(message)s"
        ))
    
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> ContextualLogger:
    """
    Get a contextual logger for the given module.
    
    Args:
        name: Logger name, typically __name__
        
    Returns:
        ContextualLogger instance
        
    Example:
        logger = get_logger(__name__)
        logger.info("Processing started", extra={"item_count": 42})
    """
    if name not in _loggers:
        base_logger = logging.getLogger(name)
        _loggers[name] = ContextualLogger(base_logger, {})
    return _loggers[name]


def set_correlation_id(correlation_id: str) -> None:
    """
    Set the correlation ID for the current context.
    
    This ID will be automatically included in all subsequent logs
    within the same async context / thread.
    
    Args:
        correlation_id: Unique identifier for request tracing
    """
    correlation_id_var.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """
    Get the current correlation ID from context.
    
    Returns:
        Current correlation ID or None if not set
    """
    return correlation_id_var.get()
