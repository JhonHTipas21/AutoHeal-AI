"""
AutoHeal AI - Log Processor
=============================

Orchestrates log processing and analysis pipeline.
Handles batching, error aggregation, and event emission.
"""

from datetime import datetime
from typing import Optional
import uuid
import httpx

from src.api.schemas import LogEntry, ErrorAnalysis
from src.core.slm_analyzer import get_slm_analyzer
from src.config import get_settings

try:
    from shared.utils.logging import get_logger
    from shared.schemas.events import LogAnalysisEvent
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)
    
    # Mock event class
    class LogAnalysisEvent:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

logger = get_logger(__name__)
settings = get_settings()


class LogProcessor:
    """
    Processes log batches through the analysis pipeline.
    
    Pipeline steps:
    1. Filter logs by relevance (errors, warnings)
    2. Analyze with SLM for classification
    3. Aggregate similar errors
    4. Emit events to Incident Manager
    """
    
    def __init__(self):
        """Initialize the log processor."""
        self.analyzer = get_slm_analyzer()
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def process_batch(self, logs: list[LogEntry]) -> list[ErrorAnalysis]:
        """
        Process a batch of log entries.
        
        Args:
            logs: List of log entries to process
            
        Returns:
            List of error analyses
        """
        if not logs:
            return []
        
        # Filter for error logs
        error_logs = [
            log for log in logs
            if log.level in ("error", "critical", "fatal")
        ]
        
        if not error_logs:
            logger.debug(f"No errors in batch of {len(logs)} logs")
            return []
        
        # Analyze with SLM
        analyses = await self.analyzer.analyze_logs(error_logs)
        
        # Emit events for critical errors
        for analysis in analyses:
            if analysis.severity in ("critical", "high"):
                await self._emit_log_analysis_event(analysis, error_logs[0])
        
        logger.info(
            f"Processed {len(logs)} logs, found {len(analyses)} error patterns",
            extra={
                "total_logs": len(logs),
                "error_logs": len(error_logs),
                "patterns": len(analyses)
            }
        )
        
        return analyses
    
    async def _emit_log_analysis_event(
        self,
        analysis: ErrorAnalysis,
        sample_log: LogEntry
    ) -> None:
        """
        Emit a log analysis event to the Incident Manager.
        
        Args:
            analysis: Error analysis result
            sample_log: Sample log entry for context
        """
        client = await self._get_client()
        
        try:
            event = {
                "event_id": str(uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "source_service": settings.service_name,
                "event_type": "log_analysis",
                "service_name": sample_log.service,
                "namespace": sample_log.namespace,
                "error_category": analysis.category.value,
                "error_count": analysis.occurrence_count,
                "severity": analysis.severity,
                "root_cause": analysis.root_cause,
                "confidence": analysis.confidence,
                "sample_message": analysis.original_message[:500],
                "recommended_actions": analysis.recommended_actions,
                "first_occurrence": analysis.first_occurrence.isoformat()
            }
            
            response = await client.post(
                f"{settings.incident_manager_url}/api/v1/events/log-analysis",
                json=event,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code in (200, 201, 202):
                logger.info(
                    f"Emitted log analysis event",
                    extra={
                        "event_id": event["event_id"],
                        "category": analysis.category.value
                    }
                )
            else:
                logger.warning(
                    f"Failed to emit event: {response.status_code}",
                    extra={"response": response.text}
                )
                
        except Exception as e:
            logger.error(f"Failed to emit log analysis event: {e}")
    
    async def process_continuous(
        self,
        service_name: str,
        namespace: str = "default",
        interval_seconds: int = 60
    ) -> None:
        """
        Continuously process logs for a service.
        
        Args:
            service_name: Service to monitor
            namespace: Kubernetes namespace
            interval_seconds: Polling interval
        """
        import asyncio
        from src.core.log_fetcher import LogFetcher
        
        fetcher = LogFetcher(settings.loki_url)
        
        logger.info(
            f"Starting continuous log processing for {service_name}",
            extra={"namespace": namespace, "interval": interval_seconds}
        )
        
        while True:
            try:
                # Fetch recent logs
                logs = await fetcher.fetch_service_logs(
                    service_name=service_name,
                    namespace=namespace,
                    time_range_minutes=int(interval_seconds / 60) + 1,
                    include_info=False,
                    max_logs=settings.log_batch_size
                )
                
                # Process the batch
                if logs:
                    await self.process_batch(logs)
                
            except Exception as e:
                logger.error(f"Error in continuous processing: {e}")
            
            await asyncio.sleep(interval_seconds)
    
    async def close(self) -> None:
        """Clean up resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
