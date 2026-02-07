"""
AutoHeal AI - Audit Store
===========================

In-memory audit record storage.
For production, use a persistent store like PostgreSQL.
"""

from datetime import datetime, timedelta
from typing import Optional
from threading import Lock

from src.api.schemas import AuditRecord, AuditEventType
from src.config import get_settings

settings = get_settings()


class AuditStore:
    """In-memory audit record storage."""
    
    def __init__(self):
        self._records: dict[str, AuditRecord] = {}
        self._lock = Lock()
    
    def add(self, record: AuditRecord) -> None:
        """Add an audit record."""
        with self._lock:
            self._records[record.record_id] = record
            
            # Prune if over limit
            if len(self._records) > settings.max_records:
                self._prune_old_records()
    
    def get(self, record_id: str) -> Optional[AuditRecord]:
        """Get a record by ID."""
        return self._records.get(record_id)
    
    def query(
        self,
        event_type: Optional[AuditEventType] = None,
        service_name: Optional[str] = None,
        incident_id: Optional[str] = None,
        healing_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> list[AuditRecord]:
        """Query records with filtering."""
        records = list(self._records.values())
        
        if event_type:
            records = [r for r in records if r.event_type == event_type]
        if service_name:
            records = [r for r in records if r.service_name == service_name]
        if incident_id:
            records = [r for r in records if r.incident_id == incident_id]
        if healing_id:
            records = [r for r in records if r.healing_id == healing_id]
        
        # Sort by timestamp descending
        records.sort(key=lambda r: r.timestamp, reverse=True)
        
        # Paginate
        start = (page - 1) * page_size
        return records[start:start + page_size]
    
    def count(
        self,
        event_type: Optional[AuditEventType] = None,
        service_name: Optional[str] = None,
        incident_id: Optional[str] = None,
        healing_id: Optional[str] = None
    ) -> int:
        """Count records with filtering."""
        records = list(self._records.values())
        
        if event_type:
            records = [r for r in records if r.event_type == event_type]
        if service_name:
            records = [r for r in records if r.service_name == service_name]
        if incident_id:
            records = [r for r in records if r.incident_id == incident_id]
        if healing_id:
            records = [r for r in records if r.healing_id == healing_id]
        
        return len(records)
    
    def count_by_event_type(self) -> dict[str, int]:
        """Count records by event type."""
        counts = {}
        for record in self._records.values():
            event = record.event_type.value
            counts[event] = counts.get(event, 0) + 1
        return counts
    
    def count_recent(self, hours: int = 24) -> int:
        """Count recent records."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return sum(1 for r in self._records.values() if r.timestamp >= cutoff)
    
    def success_rate(self) -> float:
        """Calculate success rate of actions."""
        records = [r for r in self._records.values() if r.success is not None]
        if not records:
            return 0.0
        successful = sum(1 for r in records if r.success)
        return successful / len(records)
    
    def _prune_old_records(self) -> None:
        """Remove oldest records to stay under limit."""
        if len(self._records) <= settings.max_records:
            return
        
        # Sort by timestamp and keep newest
        sorted_ids = sorted(
            self._records.keys(),
            key=lambda k: self._records[k].timestamp,
            reverse=True
        )
        
        keep = set(sorted_ids[:settings.max_records])
        self._records = {k: v for k, v in self._records.items() if k in keep}
