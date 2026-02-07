"""
AutoHeal AI - Monitoring Service API Routes
============================================

FastAPI router with endpoints for metrics, anomalies, and configuration.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

from src.config import get_settings
from src.api.schemas import (
    ServiceMetrics,
    AnomalyResponse,
    ThresholdConfig,
    ThresholdUpdateRequest,
    MetricsQueryRequest,
    MetricType,
)
from src.core.metrics_collector import MetricsCollector
from src.core.anomaly_detector import AnomalyDetector

# Try to import shared logging, fall back to standard logging
try:
    from shared.utils.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)


logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(tags=["monitoring"])

# Singleton instances (in production, use dependency injection)
_collector: MetricsCollector | None = None
_detector: AnomalyDetector | None = None


def get_collector() -> MetricsCollector:
    """Get or create the metrics collector instance."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector(settings.prometheus_url)
    return _collector


def get_detector() -> AnomalyDetector:
    """Get or create the anomaly detector instance."""
    global _detector
    if _detector is None:
        _detector = AnomalyDetector(settings)
    return _detector


# =============================================================================
# METRICS ENDPOINTS
# =============================================================================

@router.get("/metrics", response_model=list[ServiceMetrics])
async def get_all_metrics():
    """
    Retrieve current metrics for all monitored services.
    
    Returns a list of ServiceMetrics objects containing the latest
    metrics collected from Prometheus.
    """
    collector = get_collector()
    
    try:
        metrics = await collector.collect_all_metrics()
        return metrics
    except Exception as e:
        logger.error(f"Failed to collect metrics: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to collect metrics: {str(e)}"
        )


@router.post("/metrics/query", response_model=ServiceMetrics)
async def query_service_metrics(request: MetricsQueryRequest):
    """
    Query metrics for a specific service.
    
    Allows filtering by service name, namespace, and metric types.
    """
    collector = get_collector()
    
    try:
        metrics = await collector.collect_service_metrics(
            service_name=request.service_name,
            namespace=request.namespace,
            metric_types=[mt.value for mt in request.metric_types],
            time_range_minutes=request.time_range_minutes
        )
        return metrics
    except Exception as e:
        logger.error(f"Failed to query metrics: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to query metrics: {str(e)}"
        )


@router.get("/metrics/{service_name}", response_model=ServiceMetrics)
async def get_service_metrics(
    service_name: str,
    namespace: str = Query(default="default", description="Kubernetes namespace")
):
    """
    Get metrics for a specific service by name.
    
    Args:
        service_name: Name of the service to query
        namespace: Kubernetes namespace (default: "default")
    """
    collector = get_collector()
    
    try:
        metrics = await collector.collect_service_metrics(
            service_name=service_name,
            namespace=namespace
        )
        return metrics
    except Exception as e:
        logger.error(f"Failed to get service metrics: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to get service metrics: {str(e)}"
        )


# =============================================================================
# ANOMALY ENDPOINTS
# =============================================================================

@router.get("/anomalies", response_model=list[AnomalyResponse])
async def get_current_anomalies():
    """
    Get currently detected anomalies.
    
    Returns all anomalies detected in the most recent polling cycle.
    """
    collector = get_collector()
    detector = get_detector()
    
    try:
        metrics = await collector.collect_all_metrics()
        anomalies = detector.detect_anomalies(metrics)
        
        return [
            AnomalyResponse(
                anomaly_id=a.event_id,
                anomaly_type=a.anomaly_type.value,
                severity=a.severity.value,
                service_name=a.target_service,
                namespace=a.target_namespace,
                metric_name=a.metric_name,
                current_value=a.current_value,
                threshold_value=a.threshold_value,
                detected_at=a.timestamp,
                message=f"{a.anomaly_type.value}: {a.metric_name} = {a.current_value:.2f} (threshold: {a.threshold_value:.2f})"
            )
            for a in anomalies
        ]
    except Exception as e:
        logger.error(f"Failed to detect anomalies: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to detect anomalies: {str(e)}"
        )


@router.post("/anomalies/check", response_model=list[AnomalyResponse])
async def trigger_anomaly_check(background_tasks: BackgroundTasks):
    """
    Manually trigger an anomaly detection check.
    
    Collects current metrics and runs anomaly detection.
    If anomalies are found, alerts are sent to the Incident Manager.
    """
    collector = get_collector()
    detector = get_detector()
    
    try:
        metrics = await collector.collect_all_metrics()
        anomalies = detector.detect_anomalies(metrics)
        
        # Schedule alert sending in background
        if anomalies:
            from src.core.alerter import Alerter
            alerter = Alerter(settings.incident_manager_url)
            background_tasks.add_task(alerter.send_anomaly_events, anomalies)
            logger.info(f"Scheduled {len(anomalies)} anomaly alerts")
        
        return [
            AnomalyResponse(
                anomaly_id=a.event_id,
                anomaly_type=a.anomaly_type.value,
                severity=a.severity.value,
                service_name=a.target_service,
                namespace=a.target_namespace,
                metric_name=a.metric_name,
                current_value=a.current_value,
                threshold_value=a.threshold_value,
                detected_at=a.timestamp,
                message=f"{a.anomaly_type.value}: {a.metric_name} = {a.current_value:.2f} (threshold: {a.threshold_value:.2f})"
            )
            for a in anomalies
        ]
    except Exception as e:
        logger.error(f"Anomaly check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Anomaly check failed: {str(e)}"
        )


# =============================================================================
# CONFIGURATION ENDPOINTS
# =============================================================================

@router.get("/config/thresholds", response_model=ThresholdConfig)
async def get_thresholds():
    """
    Get current anomaly detection thresholds.
    
    Returns the configured threshold values used for anomaly detection.
    """
    return ThresholdConfig(
        error_rate=settings.anomaly_threshold_error_rate,
        latency_p99_ms=settings.anomaly_threshold_latency_p99_ms,
        latency_p95_ms=settings.anomaly_threshold_latency_p95_ms,
        cpu_percent=settings.anomaly_threshold_cpu_percent,
        memory_percent=settings.anomaly_threshold_memory_percent,
    )


@router.put("/config/thresholds", response_model=ThresholdConfig)
async def update_thresholds(request: ThresholdUpdateRequest):
    """
    Update anomaly detection thresholds.
    
    Note: In this implementation, threshold updates are applied to
    the in-memory detector instance. For production, consider using
    a configuration store or environment variable refresh.
    """
    detector = get_detector()
    
    # Update detector thresholds
    detector.update_thresholds(
        error_rate=request.thresholds.error_rate,
        latency_p99_ms=request.thresholds.latency_p99_ms,
        latency_p95_ms=request.thresholds.latency_p95_ms,
        cpu_percent=request.thresholds.cpu_percent,
        memory_percent=request.thresholds.memory_percent,
    )
    
    logger.info(
        "Thresholds updated",
        extra={"thresholds": request.thresholds.model_dump()}
    )
    
    return request.thresholds


# =============================================================================
# STATUS ENDPOINTS
# =============================================================================

@router.get("/status")
async def get_service_status():
    """
    Get detailed status of the monitoring service.
    
    Includes information about Prometheus connectivity,
    polling status, and recent activity.
    """
    collector = get_collector()
    detector = get_detector()
    
    # Check Prometheus connectivity
    prometheus_status = await collector.check_connection()
    
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "healthy" if prometheus_status else "degraded",
        "prometheus": {
            "url": settings.prometheus_url,
            "connected": prometheus_status
        },
        "polling": {
            "enabled": settings.polling_enabled,
            "interval_seconds": settings.polling_interval_seconds
        },
        "thresholds": {
            "error_rate": detector.thresholds.error_rate,
            "latency_p99_ms": detector.thresholds.latency_p99_ms,
            "cpu_percent": detector.thresholds.cpu_percent,
            "memory_percent": detector.thresholds.memory_percent,
        },
        "timestamp": datetime.utcnow().isoformat()
    }
