"""
AutoHeal AI - Log Parser
==========================

Parses log entries from various formats into standardized LogEntry objects.
Supports common log formats:
- JSON structured logs
- Standard text logs
- Docker container logs
- Kubernetes pod logs
"""

from datetime import datetime
from typing import Optional
import re
import json

from src.api.schemas import LogEntry, LogLevel

try:
    from shared.utils.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)

logger = get_logger(__name__)


class LogParser:
    """
    Parses log entries from various formats.
    
    Supports:
    - JSON structured logs
    - Common Log Format
    - Docker/Kubernetes JSON logs
    - Plain text with patterns
    """
    
    # Common log level mappings
    LEVEL_MAPPINGS = {
        # Standard
        "debug": LogLevel.DEBUG,
        "info": LogLevel.INFO,
        "information": LogLevel.INFO,
        "warn": LogLevel.WARNING,
        "warning": LogLevel.WARNING,
        "error": LogLevel.ERROR,
        "err": LogLevel.ERROR,
        "critical": LogLevel.CRITICAL,
        "fatal": LogLevel.CRITICAL,
        "crit": LogLevel.CRITICAL,
        "panic": LogLevel.CRITICAL,
        # Numeric
        "10": LogLevel.DEBUG,
        "20": LogLevel.INFO,
        "30": LogLevel.WARNING,
        "40": LogLevel.ERROR,
        "50": LogLevel.CRITICAL,
    }
    
    # Regex patterns for log parsing
    TIMESTAMP_PATTERNS = [
        # ISO 8601
        r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)",
        # Common log format
        r"\[(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4})\]",
        # Unix timestamp
        r"^(\d{10,13})",
    ]
    
    LEVEL_PATTERN = r"\b(DEBUG|INFO|WARN(?:ING)?|ERROR|CRITICAL|FATAL)\b"
    
    def __init__(self, default_service: str = "unknown"):
        """
        Initialize the log parser.
        
        Args:
            default_service: Default service name when not present in log
        """
        self.default_service = default_service
    
    def parse_level(self, level_str: str) -> LogLevel:
        """Parse a log level string into LogLevel enum."""
        normalized = str(level_str).lower().strip()
        return self.LEVEL_MAPPINGS.get(normalized, LogLevel.INFO)
    
    def parse_timestamp(self, ts_str: str) -> datetime:
        """Parse a timestamp string into datetime."""
        if not ts_str:
            return datetime.utcnow()
        
        # Try common formats
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(ts_str, fmt)
            except ValueError:
                continue
        
        # Try Unix timestamp
        try:
            ts_float = float(ts_str)
            if ts_float > 1e12:  # Milliseconds
                ts_float /= 1000
            return datetime.utcfromtimestamp(ts_float)
        except (ValueError, OSError):
            pass
        
        return datetime.utcnow()
    
    def parse_json_log(self, log_data: dict) -> LogEntry:
        """
        Parse a JSON structured log entry.
        
        Args:
            log_data: Dictionary containing log data
            
        Returns:
            Parsed LogEntry object
        """
        # Extract common fields with various key names
        timestamp = log_data.get("timestamp") or log_data.get("time") or log_data.get("@timestamp", "")
        level = log_data.get("level") or log_data.get("severity") or log_data.get("loglevel", "info")
        message = log_data.get("message") or log_data.get("msg") or log_data.get("log", "")
        service = log_data.get("service") or log_data.get("app") or log_data.get("application", self.default_service)
        namespace = log_data.get("namespace") or log_data.get("kubernetes", {}).get("namespace", "default")
        
        # Extract trace information
        trace_id = log_data.get("trace_id") or log_data.get("traceId")
        span_id = log_data.get("span_id") or log_data.get("spanId")
        
        # Extract exception
        exception = log_data.get("exception") or log_data.get("error") or log_data.get("stack_trace")
        if isinstance(exception, dict):
            exception = exception.get("message", str(exception))
        
        # Logger name
        logger_name = log_data.get("logger") or log_data.get("name") or log_data.get("caller")
        
        # Collect extra fields
        known_keys = {
            "timestamp", "time", "@timestamp", "level", "severity", "loglevel",
            "message", "msg", "log", "service", "app", "application", "namespace",
            "kubernetes", "trace_id", "traceId", "span_id", "spanId",
            "exception", "error", "stack_trace", "logger", "name", "caller"
        }
        extra = {k: v for k, v in log_data.items() if k not in known_keys}
        
        return LogEntry(
            timestamp=self.parse_timestamp(str(timestamp)),
            service=service,
            namespace=namespace,
            level=self.parse_level(str(level)),
            message=str(message),
            logger=logger_name,
            trace_id=trace_id,
            span_id=span_id,
            exception=str(exception) if exception else None,
            extra=extra
        )
    
    def parse_text_log(
        self,
        log_line: str,
        service: Optional[str] = None,
        namespace: str = "default"
    ) -> LogEntry:
        """
        Parse a plain text log line.
        
        Args:
            log_line: Raw log text
            service: Service name override
            namespace: Namespace override
            
        Returns:
            Parsed LogEntry object
        """
        # Try to extract timestamp
        timestamp = datetime.utcnow()
        for pattern in self.TIMESTAMP_PATTERNS:
            match = re.search(pattern, log_line)
            if match:
                timestamp = self.parse_timestamp(match.group(1))
                break
        
        # Try to extract log level
        level = LogLevel.INFO
        level_match = re.search(self.LEVEL_PATTERN, log_line, re.IGNORECASE)
        if level_match:
            level = self.parse_level(level_match.group(1))
        
        # Check for exception indicators
        exception = None
        if "exception" in log_line.lower() or "traceback" in log_line.lower():
            exception = log_line
        
        return LogEntry(
            timestamp=timestamp,
            service=service or self.default_service,
            namespace=namespace,
            level=level,
            message=log_line,
            exception=exception
        )
    
    def parse(
        self,
        log_data: str | dict,
        service: Optional[str] = None,
        namespace: str = "default"
    ) -> LogEntry:
        """
        Parse a log entry from either JSON or text format.
        
        Args:
            log_data: Log data as string or dictionary
            service: Optional service name override
            namespace: Namespace override
            
        Returns:
            Parsed LogEntry object
        """
        # If already a dict, parse as JSON
        if isinstance(log_data, dict):
            entry = self.parse_json_log(log_data)
            if service:
                entry.service = service
            if namespace != "default":
                entry.namespace = namespace
            return entry
        
        # Try to parse as JSON string
        try:
            data = json.loads(log_data)
            entry = self.parse_json_log(data)
            if service:
                entry.service = service
            if namespace != "default":
                entry.namespace = namespace
            return entry
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Fall back to text parsing
        return self.parse_text_log(str(log_data), service, namespace)
    
    def parse_batch(
        self,
        logs: list[str | dict],
        service: Optional[str] = None,
        namespace: str = "default"
    ) -> list[LogEntry]:
        """
        Parse a batch of log entries.
        
        Args:
            logs: List of log data (strings or dicts)
            service: Optional service name override
            namespace: Namespace override
            
        Returns:
            List of parsed LogEntry objects
        """
        entries = []
        for log in logs:
            try:
                entry = self.parse(log, service, namespace)
                entries.append(entry)
            except Exception as e:
                logger.warning(f"Failed to parse log entry: {e}")
                continue
        
        return entries
