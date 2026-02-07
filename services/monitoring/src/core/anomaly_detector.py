"""
AutoHeal AI - Anomaly Detector
===============================

Detects anomalies in collected metrics using configurable thresholds.
Supports multiple detection methods:
- Static thresholds
- Rate-of-change detection
- Statistical outlier detection

This module is the decision maker for when to trigger alerts.
"""

from datetime import datetime
from dataclasses import dataclass
from typing import Optional
import uuid

# Try to import shared types and logging
try:
    from shared.constants import AnomalyType, Severity
    from shared.schemas.events import AnomalyEvent
    from shared.utils.logging import get_logger
except ImportError:
    # Fallback definitions for standalone testing
    import logging
    from enum import Enum
    
    def get_logger(name: str):
        return logging.getLogger(name)
    
    class AnomalyType(str, Enum):
        ERROR_RATE_SPIKE = "error_rate_spike"
        LATENCY_SPIKE = "latency_spike"
        CPU_OVERLOAD = "cpu_overload"
        MEMORY_OVERLOAD = "memory_overload"
        POD_CRASH_LOOP = "pod_crash_loop"
    
    class Severity(str, Enum):
        CRITICAL = "critical"
        HIGH = "high"
        MEDIUM = "medium"
        LOW = "low"
        INFO = "info"
    
    # Simple event class for standalone mode
    @dataclass
    class AnomalyEvent:
        event_id: str
        timestamp: datetime
        source_service: str
        anomaly_type: AnomalyType
        severity: Severity
        target_service: str
        target_namespace: str
        metric_name: str
        current_value: float
        threshold_value: float
        correlation_id: Optional[str] = None
        threshold_direction: str = "above"
        metric_window_seconds: int = 60
        additional_context: dict = None

from src.api.schemas import ServiceMetrics, MetricValue, MetricType

logger = get_logger(__name__)


@dataclass
class ThresholdConfig:
    """Configuration for anomaly detection thresholds."""
    error_rate: float = 0.05  # 5%
    latency_p99_ms: int = 1000
    latency_p95_ms: int = 500
    cpu_percent: int = 80
    memory_percent: int = 85
    pod_restart_count: int = 3


class AnomalyDetector:
    """
    Detects anomalies in metrics using threshold-based detection.
    
    The detector compares current metric values against configured
    thresholds and generates AnomalyEvent objects for violations.
    
    Future enhancements could include:
    - Machine learning-based anomaly detection
    - Seasonal patterns detection
    - Correlation across multiple metrics
    
    Example:
        detector = AnomalyDetector(settings)
        anomalies = detector.detect_anomalies(metrics)
    """
    
    def __init__(self, settings):
        """
        Initialize the anomaly detector.
        
        Args:
            settings: Configuration settings with threshold values
        """
        self.thresholds = ThresholdConfig(
            error_rate=getattr(settings, 'anomaly_threshold_error_rate', 0.05),
            latency_p99_ms=getattr(settings, 'anomaly_threshold_latency_p99_ms', 1000),
            latency_p95_ms=getattr(settings, 'anomaly_threshold_latency_p95_ms', 500),
            cpu_percent=getattr(settings, 'anomaly_threshold_cpu_percent', 80),
            memory_percent=getattr(settings, 'anomaly_threshold_memory_percent', 85),
        )
        
        # Track recent anomalies for deduplication
        self._recent_anomalies: dict[str, datetime] = {}
        self._cooldown_seconds = getattr(settings, 'alert_cooldown_seconds', 60)
    
    def update_thresholds(
        self,
        error_rate: Optional[float] = None,
        latency_p99_ms: Optional[int] = None,
        latency_p95_ms: Optional[int] = None,
        cpu_percent: Optional[int] = None,
        memory_percent: Optional[int] = None,
    ) -> None:
        """
        Update detection thresholds dynamically.
        
        Args:
            error_rate: New error rate threshold
            latency_p99_ms: New P99 latency threshold
            latency_p95_ms: New P95 latency threshold
            cpu_percent: New CPU threshold
            memory_percent: New memory threshold
        """
        if error_rate is not None:
            self.thresholds.error_rate = error_rate
        if latency_p99_ms is not None:
            self.thresholds.latency_p99_ms = latency_p99_ms
        if latency_p95_ms is not None:
            self.thresholds.latency_p95_ms = latency_p95_ms
        if cpu_percent is not None:
            self.thresholds.cpu_percent = cpu_percent
        if memory_percent is not None:
            self.thresholds.memory_percent = memory_percent
        
        logger.info(
            "Thresholds updated",
            extra={"thresholds": self.thresholds}
        )
    
    def _generate_anomaly_key(
        self,
        service: str,
        namespace: str,
        anomaly_type: AnomalyType
    ) -> str:
        """Generate a unique key for anomaly deduplication."""
        return f"{namespace}:{service}:{anomaly_type.value}"
    
    def _is_in_cooldown(self, anomaly_key: str) -> bool:
        """Check if an anomaly is in cooldown period."""
        if anomaly_key not in self._recent_anomalies:
            return False
        
        last_time = self._recent_anomalies[anomaly_key]
        elapsed = (datetime.utcnow() - last_time).total_seconds()
        
        return elapsed < self._cooldown_seconds
    
    def _record_anomaly(self, anomaly_key: str) -> None:
        """Record an anomaly for cooldown tracking."""
        self._recent_anomalies[anomaly_key] = datetime.utcnow()
    
    def _determine_severity(
        self,
        anomaly_type: AnomalyType,
        current_value: float,
        threshold_value: float
    ) -> Severity:
        """
        Determine severity based on how much the threshold is exceeded.
        
        Args:
            anomaly_type: Type of anomaly
            current_value: Current metric value
            threshold_value: Threshold that was exceeded
            
        Returns:
            Calculated severity level
        """
        if threshold_value == 0:
            ratio = float('inf')
        else:
            ratio = current_value / threshold_value
        
        # Error rates are critical if over 20%, high if over 10%
        if anomaly_type == AnomalyType.ERROR_RATE_SPIKE:
            if ratio >= 4:  # 4x threshold (e.g., 20% if threshold is 5%)
                return Severity.CRITICAL
            elif ratio >= 2:  # 2x threshold (e.g., 10% if threshold is 5%)
                return Severity.HIGH
            else:
                return Severity.MEDIUM
        
        # Latency severity based on multiplier
        if anomaly_type == AnomalyType.LATENCY_SPIKE:
            if ratio >= 3:
                return Severity.HIGH
            elif ratio >= 2:
                return Severity.MEDIUM
            else:
                return Severity.LOW
        
        # Resource usage severity
        if anomaly_type in (AnomalyType.CPU_OVERLOAD, AnomalyType.MEMORY_OVERLOAD):
            if current_value >= 95:
                return Severity.CRITICAL
            elif current_value >= 90:
                return Severity.HIGH
            else:
                return Severity.MEDIUM
        
        return Severity.MEDIUM
    
    def _create_anomaly_event(
        self,
        anomaly_type: AnomalyType,
        service_name: str,
        namespace: str,
        metric_name: str,
        current_value: float,
        threshold_value: float,
        additional_context: Optional[dict] = None
    ) -> AnomalyEvent:
        """Create an AnomalyEvent object."""
        severity = self._determine_severity(
            anomaly_type, current_value, threshold_value
        )
        
        return AnomalyEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            source_service="monitoring",
            correlation_id=None,
            anomaly_type=anomaly_type,
            severity=severity,
            target_service=service_name,
            target_namespace=namespace,
            metric_name=metric_name,
            current_value=current_value,
            threshold_value=threshold_value,
            threshold_direction="above",
            metric_window_seconds=300,  # 5 minutes
            additional_context=additional_context or {}
        )
    
    def detect_anomalies(
        self,
        service_metrics: list[ServiceMetrics]
    ) -> list[AnomalyEvent]:
        """
        Detect anomalies in the provided metrics.
        
        Iterates through all metrics and compares against thresholds.
        Applies cooldown to prevent duplicate alerts.
        
        Args:
            service_metrics: List of ServiceMetrics to analyze
            
        Returns:
            List of detected AnomalyEvent objects
        """
        anomalies: list[AnomalyEvent] = []
        
        for service in service_metrics:
            for metric in service.metrics:
                detected = self._check_metric(
                    metric,
                    service.service_name,
                    service.namespace
                )
                
                if detected:
                    # Check cooldown
                    anomaly_key = self._generate_anomaly_key(
                        service.service_name,
                        service.namespace,
                        detected.anomaly_type
                    )
                    
                    if not self._is_in_cooldown(anomaly_key):
                        anomalies.append(detected)
                        self._record_anomaly(anomaly_key)
                        
                        logger.info(
                            f"Anomaly detected: {detected.anomaly_type.value}",
                            extra={
                                "service": service.service_name,
                                "namespace": service.namespace,
                                "metric": detected.metric_name,
                                "value": detected.current_value,
                                "threshold": detected.threshold_value,
                                "severity": detected.severity.value
                            }
                        )
                    else:
                        logger.debug(
                            f"Anomaly in cooldown: {anomaly_key}"
                        )
        
        return anomalies
    
    def _check_metric(
        self,
        metric: MetricValue,
        service_name: str,
        namespace: str
    ) -> Optional[AnomalyEvent]:
        """
        Check a single metric against thresholds.
        
        Args:
            metric: The metric to check
            service_name: Name of the service
            namespace: Kubernetes namespace
            
        Returns:
            AnomalyEvent if threshold exceeded, None otherwise
        """
        # Error rate check
        if metric.metric_type == MetricType.ERROR_RATE:
            if metric.value > self.thresholds.error_rate:
                return self._create_anomaly_event(
                    anomaly_type=AnomalyType.ERROR_RATE_SPIKE,
                    service_name=service_name,
                    namespace=namespace,
                    metric_name="error_rate",
                    current_value=metric.value,
                    threshold_value=self.thresholds.error_rate,
                    additional_context={"labels": metric.labels}
                )
        
        # P99 latency check
        elif metric.metric_type == MetricType.LATENCY_P99:
            if metric.value > self.thresholds.latency_p99_ms:
                return self._create_anomaly_event(
                    anomaly_type=AnomalyType.LATENCY_SPIKE,
                    service_name=service_name,
                    namespace=namespace,
                    metric_name="latency_p99_ms",
                    current_value=metric.value,
                    threshold_value=self.thresholds.latency_p99_ms,
                    additional_context={"percentile": "p99"}
                )
        
        # P95 latency check
        elif metric.metric_type == MetricType.LATENCY_P95:
            if metric.value > self.thresholds.latency_p95_ms:
                return self._create_anomaly_event(
                    anomaly_type=AnomalyType.LATENCY_SPIKE,
                    service_name=service_name,
                    namespace=namespace,
                    metric_name="latency_p95_ms",
                    current_value=metric.value,
                    threshold_value=self.thresholds.latency_p95_ms,
                    additional_context={"percentile": "p95"}
                )
        
        # CPU usage check
        elif metric.metric_type == MetricType.CPU_USAGE:
            if metric.value > self.thresholds.cpu_percent:
                return self._create_anomaly_event(
                    anomaly_type=AnomalyType.CPU_OVERLOAD,
                    service_name=service_name,
                    namespace=namespace,
                    metric_name="cpu_percent",
                    current_value=metric.value,
                    threshold_value=self.thresholds.cpu_percent
                )
        
        # Memory usage check
        elif metric.metric_type == MetricType.MEMORY_USAGE:
            if metric.value > self.thresholds.memory_percent:
                return self._create_anomaly_event(
                    anomaly_type=AnomalyType.MEMORY_OVERLOAD,
                    service_name=service_name,
                    namespace=namespace,
                    metric_name="memory_percent",
                    current_value=metric.value,
                    threshold_value=self.thresholds.memory_percent
                )
        
        # Pod restart check
        elif metric.metric_type == MetricType.POD_RESTART_COUNT:
            if metric.value > self.thresholds.pod_restart_count:
                return self._create_anomaly_event(
                    anomaly_type=AnomalyType.POD_CRASH_LOOP,
                    service_name=service_name,
                    namespace=namespace,
                    metric_name="pod_restart_count",
                    current_value=metric.value,
                    threshold_value=self.thresholds.pod_restart_count
                )
        
        return None
