"""
AutoHeal AI - Event Correlator
================================

Correlates multiple events to identify related incidents.
Uses time-based and service-based correlation strategies.
"""

from datetime import datetime, timedelta
from typing import Optional

from src.api.schemas import AnomalyEventInput, LogAnalysisEventInput

try:
    from shared.utils.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)

logger = get_logger(__name__)


class EventCorrelator:
    """
    Correlates events from different sources.
    
    Strategies:
    1. Time-based: Events within a time window
    2. Service-based: Events affecting same service
    3. Namespace-based: Events in same namespace
    """
    
    def __init__(self, correlation_window_minutes: int = 15):
        self.correlation_window = timedelta(minutes=correlation_window_minutes)
        self._event_history: list[dict] = []
    
    def add_event(self, event: dict) -> None:
        """Add an event to history for correlation."""
        event["_added_at"] = datetime.utcnow()
        self._event_history.append(event)
        
        # Prune old events
        cutoff = datetime.utcnow() - self.correlation_window * 2
        self._event_history = [
            e for e in self._event_history
            if e["_added_at"] >= cutoff
        ]
    
    def find_related_events(
        self,
        service: str,
        namespace: str = "default",
        since: Optional[datetime] = None
    ) -> list[dict]:
        """Find events related to a service."""
        if since is None:
            since = datetime.utcnow() - self.correlation_window
        
        return [
            e for e in self._event_history
            if e.get("target_service") == service
            or e.get("service_name") == service
            and e["_added_at"] >= since
        ]
    
    def calculate_correlation_score(
        self,
        event1: dict,
        event2: dict
    ) -> float:
        """
        Calculate correlation score between two events.
        
        Returns a score from 0 to 1.
        """
        score = 0.0
        
        # Same service: high correlation
        svc1 = event1.get("target_service") or event1.get("service_name")
        svc2 = event2.get("target_service") or event2.get("service_name")
        if svc1 and svc2 and svc1 == svc2:
            score += 0.5
        
        # Same namespace
        ns1 = event1.get("target_namespace") or event1.get("namespace")
        ns2 = event2.get("target_namespace") or event2.get("namespace")
        if ns1 and ns2 and ns1 == ns2:
            score += 0.2
        
        # Time proximity
        ts1 = event1.get("timestamp") or event1.get("_added_at")
        ts2 = event2.get("timestamp") or event2.get("_added_at")
        if ts1 and ts2:
            if isinstance(ts1, str):
                ts1 = datetime.fromisoformat(ts1.replace("Z", ""))
            if isinstance(ts2, str):
                ts2 = datetime.fromisoformat(ts2.replace("Z", ""))
            
            time_diff = abs((ts1 - ts2).total_seconds())
            if time_diff < 60:  # Within 1 minute
                score += 0.3
            elif time_diff < 300:  # Within 5 minutes
                score += 0.2
            elif time_diff < 900:  # Within 15 minutes
                score += 0.1
        
        return min(score, 1.0)
