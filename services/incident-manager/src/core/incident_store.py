"""
AutoHeal AI - Incident Store
==============================

In-memory incident storage for development.
For production, this would be backed by PostgreSQL or Redis.
"""

from datetime import datetime, timedelta
from typing import Optional
from threading import Lock

from src.api.schemas import Incident, IncidentStatus, IncidentSeverity

try:
    from shared.utils.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)

logger = get_logger(__name__)


class IncidentStore:
    """
    Thread-safe in-memory incident storage.
    
    Provides CRUD operations and query capabilities.
    """
    
    def __init__(self):
        self._incidents: dict[str, Incident] = {}
        self._lock = Lock()
    
    def create_incident(self, incident: Incident) -> Incident:
        """Create a new incident."""
        with self._lock:
            self._incidents[incident.incident_id] = incident
            logger.info(f"Created incident {incident.incident_id}")
            return incident
    
    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get an incident by ID."""
        return self._incidents.get(incident_id)
    
    def update_incident(
        self,
        incident_id: str,
        updates: dict
    ) -> Optional[Incident]:
        """Update an incident."""
        with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                return None
            
            # Apply updates
            incident_dict = incident.model_dump()
            incident_dict.update(updates)
            incident_dict["updated_at"] = datetime.utcnow()
            
            updated = Incident(**incident_dict)
            self._incidents[incident_id] = updated
            
            return updated
    
    def delete_incident(self, incident_id: str) -> bool:
        """Delete an incident."""
        with self._lock:
            if incident_id in self._incidents:
                del self._incidents[incident_id]
                return True
            return False
    
    def add_event_to_incident(
        self,
        incident_id: str,
        event_id: str
    ) -> Optional[Incident]:
        """Add an event to an incident."""
        with self._lock:
            incident = self._incidents.get(incident_id)
            if not incident:
                return None
            
            incident.event_ids.append(event_id)
            incident.event_count = len(incident.event_ids)
            incident.updated_at = datetime.utcnow()
            
            return incident
    
    def find_related_incident(
        self,
        service: str,
        namespace: str = "default",
        window_minutes: int = 15
    ) -> Optional[Incident]:
        """
        Find a related active incident for correlation.
        
        Args:
            service: Target service name
            namespace: Kubernetes namespace
            window_minutes: Time window for correlation
            
        Returns:
            Related incident if found, None otherwise
        """
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        
        for incident in self._incidents.values():
            # Check if incident is active and matches criteria
            if (
                incident.status not in (IncidentStatus.RESOLVED, IncidentStatus.FAILED)
                and incident.target_service == service
                and incident.target_namespace == namespace
                and incident.created_at >= cutoff
            ):
                return incident
        
        return None
    
    def list_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        severity: Optional[IncidentSeverity] = None,
        service: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> list[Incident]:
        """List incidents with optional filtering."""
        incidents = list(self._incidents.values())
        
        # Apply filters
        if status:
            incidents = [i for i in incidents if i.status == status]
        if severity:
            incidents = [i for i in incidents if i.severity == severity]
        if service:
            incidents = [i for i in incidents if i.target_service == service]
        
        # Sort by created_at descending
        incidents.sort(key=lambda i: i.created_at, reverse=True)
        
        # Paginate
        start = (page - 1) * page_size
        end = start + page_size
        
        return incidents[start:end]
    
    def count_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        severity: Optional[IncidentSeverity] = None,
        service: Optional[str] = None
    ) -> int:
        """Count incidents with optional filtering."""
        incidents = list(self._incidents.values())
        
        if status:
            incidents = [i for i in incidents if i.status == status]
        if severity:
            incidents = [i for i in incidents if i.severity == severity]
        if service:
            incidents = [i for i in incidents if i.target_service == service]
        
        return len(incidents)
    
    def count_active(self) -> int:
        """Count active (unresolved) incidents."""
        return sum(
            1 for i in self._incidents.values()
            if i.status not in (IncidentStatus.RESOLVED, IncidentStatus.FAILED)
        )
    
    def count_by_status(self) -> dict[str, int]:
        """Count incidents by status."""
        counts = {}
        for incident in self._incidents.values():
            status = incident.status.value
            counts[status] = counts.get(status, 0) + 1
        return counts
    
    def count_by_severity(self) -> dict[str, int]:
        """Count incidents by severity."""
        counts = {}
        for incident in self._incidents.values():
            severity = incident.severity.value
            counts[severity] = counts.get(severity, 0) + 1
        return counts
    
    def count_recent(self, hours: int = 24) -> int:
        """Count incidents from the last N hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return sum(
            1 for i in self._incidents.values()
            if i.created_at >= cutoff
        )
