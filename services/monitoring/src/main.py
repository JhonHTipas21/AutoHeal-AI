"""
AutoHeal AI - Monitoring Service Main Application
==================================================

FastAPI application entry point for the Monitoring Service.
Handles metrics collection, anomaly detection, and alerting.

Responsibilities:
- Collect metrics from Prometheus
- Detect anomalies using configurable thresholds
- Send anomaly events to the Incident Manager
- Expose health and metrics endpoints
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid

# Local imports
from src.config import get_settings
from src.api.routes import router as api_router

# Import shared utilities - handle case where shared might not be available
try:
    from shared.utils.logging import setup_logging, get_logger, set_correlation_id
except ImportError:
    # Fallback for when shared module is not in path
    import logging
    import sys
    
    def setup_logging(service_name: str, log_level: str = "INFO", json_output: bool = True):
        logging.basicConfig(
            level=getattr(logging, log_level),
            format=f"%(asctime)s | {service_name} | %(levelname)s | %(name)s | %(message)s",
            stream=sys.stdout
        )
    
    def get_logger(name: str):
        return logging.getLogger(name)
    
    def set_correlation_id(cid: str):
        pass


settings = get_settings()

# Initialize logging
setup_logging(
    service_name=settings.service_name,
    log_level=settings.log_level,
    json_output=settings.log_json
)

logger = get_logger(__name__)


# Background task reference
_polling_task: asyncio.Task | None = None


async def start_metric_polling():
    """
    Start the background metric polling loop.
    
    This coroutine runs continuously, polling Prometheus for metrics
    and triggering anomaly detection on each poll cycle.
    """
    from src.core.metrics_collector import MetricsCollector
    from src.core.anomaly_detector import AnomalyDetector
    from src.core.alerter import Alerter
    
    logger.info(
        f"Starting metric polling with {settings.polling_interval_seconds}s interval"
    )
    
    collector = MetricsCollector(settings.prometheus_url)
    detector = AnomalyDetector(settings)
    alerter = Alerter(settings.incident_manager_url)
    
    while True:
        try:
            # Collect current metrics
            metrics = await collector.collect_all_metrics()
            
            if metrics:
                logger.debug(
                    f"Collected {len(metrics)} metrics",
                    extra={"metric_count": len(metrics)}
                )
                
                # Detect anomalies
                anomalies = detector.detect_anomalies(metrics)
                
                if anomalies:
                    logger.info(
                        f"Detected {len(anomalies)} anomalies",
                        extra={"anomaly_count": len(anomalies)}
                    )
                    
                    # Send alerts
                    await alerter.send_anomaly_events(anomalies)
            
        except Exception as e:
            logger.error(
                f"Error in metric polling loop: {e}",
                extra={"error": str(e)}
            )
        
        # Wait for next polling interval
        await asyncio.sleep(settings.polling_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events:
    - Startup: Initialize connections, start background tasks
    - Shutdown: Clean up resources, stop background tasks
    """
    global _polling_task
    
    logger.info(
        f"Starting {settings.service_name} v{settings.service_version}",
        extra={"version": settings.service_version}
    )
    
    # Start metric polling if enabled
    if settings.polling_enabled:
        _polling_task = asyncio.create_task(start_metric_polling())
        logger.info("Metric polling task started")
    else:
        logger.info("Metric polling is disabled")
    
    yield
    
    # Shutdown
    logger.info("Shutting down monitoring service...")
    
    if _polling_task:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            logger.info("Polling task cancelled")
    
    logger.info("Monitoring service shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="AutoHeal AI - Monitoring Service",
    description="Metrics collection, anomaly detection, and alerting for AutoHeal AI",
    version=settings.service_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """
    Middleware to extract or generate correlation ID for tracing.
    
    The correlation ID is propagated through all service calls
    to enable distributed tracing.
    """
    # Get correlation ID from header or generate new one
    correlation_id = request.headers.get("X-Correlation-ID")
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    
    # Set correlation ID in context
    set_correlation_id(correlation_id)
    
    # Process request
    response = await call_next(request)
    
    # Add correlation ID to response
    response.headers["X-Correlation-ID"] = correlation_id
    
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled errors.
    
    Logs the error and returns a standardized error response.
    """
    logger.error(
        f"Unhandled exception: {exc}",
        extra={"path": request.url.path, "error": str(exc)},
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "detail": str(exc) if settings.debug else None
        }
    )


# Health check endpoint (at root level)
@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint for container orchestration.
    
    Returns service status and version information.
    Used by Docker health checks and Kubernetes probes.
    """
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.service_version
    }


@app.get("/ready", tags=["health"])
async def readiness_check():
    """
    Readiness check endpoint.
    
    Verifies that the service is ready to accept traffic,
    including checking downstream dependencies.
    """
    # TODO: Add actual dependency checks (Prometheus connectivity, etc.)
    return {
        "status": "ready",
        "service": settings.service_name,
        "polling_active": _polling_task is not None and not _polling_task.done()
    }


# Include API routes
app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
