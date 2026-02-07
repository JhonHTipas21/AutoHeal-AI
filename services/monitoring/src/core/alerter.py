"""
AutoHeal AI - Alerter
======================

Sends anomaly events to the Incident Manager service.
Handles batching, retries, and failure logging.
"""

from datetime import datetime
from typing import Optional
import httpx

# Try to import shared types and logging
try:
    from shared.schemas.events import AnomalyEvent
    from shared.utils.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)

logger = get_logger(__name__)


class Alerter:
    """
    Sends anomaly alerts to the Incident Manager.
    
    Responsibilities:
    - Serialize AnomalyEvent objects to JSON
    - Send HTTP POST requests to the Incident Manager
    - Handle failures gracefully with logging
    - Support batch sending for efficiency
    
    Example:
        alerter = Alerter("http://incident-manager:8002")
        await alerter.send_anomaly_events(anomalies)
    """
    
    def __init__(
        self,
        incident_manager_url: str,
        timeout_seconds: float = 10.0,
        max_retries: int = 3
    ):
        """
        Initialize the alerter.
        
        Args:
            incident_manager_url: URL of the Incident Manager service
            timeout_seconds: HTTP request timeout
            max_retries: Maximum retry attempts for failed sends
        """
        self.incident_manager_url = incident_manager_url.rstrip("/")
        self.timeout = timeout_seconds
        self.max_retries = max_retries
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create an HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout)
            )
        return self._client
    
    def _serialize_event(self, event) -> dict:
        """
        Serialize an AnomalyEvent to a dictionary.
        
        Handles both Pydantic models and dataclasses.
        """
        # Try Pydantic v2 method
        if hasattr(event, 'model_dump'):
            return event.model_dump(mode='json')
        # Try Pydantic v1 method
        elif hasattr(event, 'dict'):
            data = event.dict()
            # Convert datetime objects
            for key, value in data.items():
                if isinstance(value, datetime):
                    data[key] = value.isoformat()
            return data
        # Dataclass fallback
        elif hasattr(event, '__dataclass_fields__'):
            import dataclasses
            data = dataclasses.asdict(event)
            for key, value in data.items():
                if isinstance(value, datetime):
                    data[key] = value.isoformat()
                elif hasattr(value, 'value'):  # Enum
                    data[key] = value.value
            return data
        else:
            raise ValueError(f"Cannot serialize event type: {type(event)}")
    
    async def send_anomaly_event(self, event) -> bool:
        """
        Send a single anomaly event to the Incident Manager.
        
        Args:
            event: AnomalyEvent to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        client = await self._get_client()
        
        try:
            payload = self._serialize_event(event)
            
            response = await client.post(
                f"{self.incident_manager_url}/api/v1/events/anomaly",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Source-Service": "monitoring"
                }
            )
            
            if response.status_code in (200, 201, 202):
                logger.info(
                    f"Anomaly event sent successfully",
                    extra={
                        "event_id": event.event_id,
                        "anomaly_type": event.anomaly_type.value if hasattr(event.anomaly_type, 'value') else event.anomaly_type,
                        "service": event.target_service
                    }
                )
                return True
            else:
                logger.warning(
                    f"Failed to send anomaly event: {response.status_code}",
                    extra={
                        "event_id": event.event_id,
                        "status_code": response.status_code,
                        "response": response.text
                    }
                )
                return False
                
        except httpx.HTTPError as e:
            logger.error(
                f"HTTP error sending anomaly event: {e}",
                extra={"event_id": event.event_id, "error": str(e)}
            )
            return False
        except Exception as e:
            logger.error(
                f"Error sending anomaly event: {e}",
                extra={"event_id": event.event_id, "error": str(e)}
            )
            return False
    
    async def send_anomaly_events(self, events: list) -> dict:
        """
        Send multiple anomaly events to the Incident Manager.
        
        Sends events sequentially and tracks success/failure counts.
        In production, consider implementing batch endpoints.
        
        Args:
            events: List of AnomalyEvent objects to send
            
        Returns:
            Dictionary with 'sent' and 'failed' counts
        """
        if not events:
            return {"sent": 0, "failed": 0}
        
        sent = 0
        failed = 0
        
        for event in events:
            success = await self.send_anomaly_event(event)
            if success:
                sent += 1
            else:
                failed += 1
        
        logger.info(
            f"Batch alert complete",
            extra={
                "total": len(events),
                "sent": sent,
                "failed": failed
            }
        )
        
        return {"sent": sent, "failed": failed}
    
    async def check_incident_manager_health(self) -> bool:
        """
        Check if the Incident Manager is reachable.
        
        Returns:
            True if healthy, False otherwise
        """
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"{self.incident_manager_url}/health"
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(
                f"Incident Manager health check failed: {e}"
            )
            return False
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
