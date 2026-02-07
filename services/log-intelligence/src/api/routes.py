"""
AutoHeal AI - Log Intelligence API Routes
==========================================

FastAPI endpoints for log ingestion and analysis.
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
import uuid

from src.config import get_settings
from src.api.schemas import (
    LogEntry,
    LogBatch,
    AnalysisRequest,
    AnalysisResponse,
    ErrorAnalysis,
)

try:
    from shared.utils.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(tags=["log-intelligence"])


# =============================================================================
# LOG INGESTION ENDPOINTS
# =============================================================================

@router.post("/logs/ingest", status_code=202)
async def ingest_logs(
    batch: LogBatch,
    background_tasks: BackgroundTasks
):
    """
    Ingest a batch of logs for analysis.
    
    Logs are queued for processing and analyzed asynchronously.
    """
    from src.core.log_processor import LogProcessor
    
    processor = LogProcessor()
    
    # Process in background
    background_tasks.add_task(processor.process_batch, batch.logs)
    
    logger.info(
        f"Queued {len(batch.logs)} logs for processing",
        extra={"log_count": len(batch.logs), "source": batch.source}
    )
    
    return {
        "status": "accepted",
        "message": f"Queued {len(batch.logs)} logs for processing",
        "batch_id": str(uuid.uuid4())
    }


@router.post("/logs/analyze", response_model=AnalysisResponse)
async def analyze_logs(batch: LogBatch):
    """
    Analyze a batch of logs synchronously.
    
    Returns detailed analysis including error classification
    and root cause inference.
    """
    from src.core.log_processor import LogProcessor
    from src.core.slm_analyzer import get_slm_analyzer
    
    processor = LogProcessor()
    analyzer = get_slm_analyzer()
    
    # Filter error logs
    error_logs = [
        log for log in batch.logs 
        if log.level in ("error", "critical")
    ]
    
    if not error_logs:
        return AnalysisResponse(
            analysis_id=str(uuid.uuid4()),
            service_name=batch.logs[0].service if batch.logs else "unknown",
            namespace=batch.logs[0].namespace if batch.logs else "default",
            total_logs_analyzed=len(batch.logs),
            error_count=0,
            errors=[],
            summary="No errors found in the provided logs.",
            slm_provider=settings.slm_provider.value
        )
    
    # Analyze errors with SLM
    analyses = await analyzer.analyze_logs(error_logs)
    
    # Get primary service name
    service_name = error_logs[0].service
    namespace = error_logs[0].namespace
    
    return AnalysisResponse(
        analysis_id=str(uuid.uuid4()),
        service_name=service_name,
        namespace=namespace,
        total_logs_analyzed=len(batch.logs),
        error_count=len(error_logs),
        errors=analyses,
        summary=f"Analyzed {len(error_logs)} errors. Found {len(analyses)} distinct error patterns.",
        slm_provider=settings.slm_provider.value
    )


# =============================================================================
# ANALYSIS ENDPOINTS
# =============================================================================

@router.post("/analyze/service", response_model=AnalysisResponse)
async def analyze_service_logs(request: AnalysisRequest):
    """
    Analyze logs for a specific service.
    
    Fetches logs from Loki and performs analysis.
    """
    from src.core.log_fetcher import LogFetcher
    from src.core.slm_analyzer import get_slm_analyzer
    
    fetcher = LogFetcher(settings.loki_url)
    analyzer = get_slm_analyzer()
    
    # Fetch logs from Loki
    try:
        logs = await fetcher.fetch_service_logs(
            service_name=request.service_name,
            namespace=request.namespace,
            time_range_minutes=request.time_range_minutes,
            include_info=request.include_info,
            max_logs=request.max_logs
        )
    except Exception as e:
        logger.error(f"Failed to fetch logs from Loki: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch logs: {str(e)}"
        )
    
    if not logs:
        return AnalysisResponse(
            analysis_id=str(uuid.uuid4()),
            service_name=request.service_name,
            namespace=request.namespace,
            total_logs_analyzed=0,
            error_count=0,
            errors=[],
            summary="No logs found for the specified service and time range.",
            slm_provider=settings.slm_provider.value
        )
    
    # Filter for errors
    error_logs = [log for log in logs if log.level in ("error", "critical")]
    
    # Analyze with SLM
    analyses = await analyzer.analyze_logs(error_logs) if error_logs else []
    
    return AnalysisResponse(
        analysis_id=str(uuid.uuid4()),
        service_name=request.service_name,
        namespace=request.namespace,
        total_logs_analyzed=len(logs),
        error_count=len(error_logs),
        errors=analyses,
        summary=f"Analyzed {len(logs)} logs, found {len(error_logs)} errors with {len(analyses)} distinct patterns.",
        slm_provider=settings.slm_provider.value
    )


@router.get("/analyze/{service_name}", response_model=AnalysisResponse)
async def get_service_analysis(
    service_name: str,
    namespace: str = Query(default="default"),
    time_range: int = Query(default=30, ge=1, le=1440)
):
    """
    Get analysis for a service (convenience endpoint).
    """
    request = AnalysisRequest(
        service_name=service_name,
        namespace=namespace,
        time_range_minutes=time_range
    )
    return await analyze_service_logs(request)


# =============================================================================
# COMMIT CORRELATION ENDPOINTS
# =============================================================================

@router.post("/correlate/commits")
async def correlate_with_commits(
    error_pattern: str,
    service_name: str,
    time_window_minutes: int = Query(default=60, ge=1, le=1440)
):
    """
    Correlate an error pattern with recent commits.
    
    Analyzes git history to find commits that may have
    introduced the error.
    """
    from src.core.commit_correlator import CommitCorrelator
    
    correlator = CommitCorrelator()
    
    try:
        result = await correlator.correlate(
            error_pattern=error_pattern,
            service_name=service_name,
            time_window_minutes=time_window_minutes
        )
        return result
    except Exception as e:
        logger.error(f"Commit correlation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Correlation failed: {str(e)}"
        )


# =============================================================================
# STATUS AND CONFIGURATION
# =============================================================================

@router.get("/status")
async def get_service_status():
    """Get detailed status of the log intelligence service."""
    from src.core.slm_analyzer import get_slm_analyzer
    from src.core.log_fetcher import LogFetcher
    
    analyzer = get_slm_analyzer()
    fetcher = LogFetcher(settings.loki_url)
    
    # Check Loki connectivity
    loki_status = await fetcher.check_connection()
    
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "healthy" if analyzer.is_ready() else "degraded",
        "slm": {
            "provider": settings.slm_provider.value,
            "model": settings.slm_model_name,
            "ready": analyzer.is_ready()
        },
        "loki": {
            "url": settings.loki_url,
            "connected": loki_status
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/config")
async def get_configuration():
    """Get current service configuration."""
    return {
        "slm_provider": settings.slm_provider.value,
        "slm_model": settings.slm_model_name,
        "slm_max_tokens": settings.slm_max_tokens,
        "slm_temperature": settings.slm_temperature,
        "log_batch_size": settings.log_batch_size,
        "log_retention_hours": settings.log_retention_hours,
        "error_correlation_window_minutes": settings.error_correlation_window_minutes
    }
