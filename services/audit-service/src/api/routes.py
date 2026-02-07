"""
AutoHeal AI - Audit Service API Routes
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Query
import uuid

from src.api.schemas import (
    AuditRecord,
    CreateAuditRecord,
    AuditListResponse,
    AuditEventType,
)
from src.config import get_settings

try:
    from shared.utils.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter()


@router.post("/records", response_model=AuditRecord, status_code=201, tags=["audit"])
async def create_audit_record(record: CreateAuditRecord, request: Request):
    """Create a new audit record."""
    store = request.app.state.audit_store
    
    audit_record = AuditRecord(
        record_id=str(uuid.uuid4()),
        **record.model_dump(),
        correlation_id=request.headers.get("X-Correlation-ID")
    )
    
    store.add(audit_record)
    
    logger.info(
        f"Audit record created: {audit_record.event_type.value}",
        extra={"record_id": audit_record.record_id}
    )
    
    return audit_record


@router.get("/records", response_model=AuditListResponse, tags=["audit"])
async def list_audit_records(
    request: Request,
    event_type: Optional[AuditEventType] = None,
    service_name: Optional[str] = None,
    incident_id: Optional[str] = None,
    healing_id: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100)
):
    """List audit records with optional filtering."""
    store = request.app.state.audit_store
    
    records = store.query(
        event_type=event_type,
        service_name=service_name,
        incident_id=incident_id,
        healing_id=healing_id,
        page=page,
        page_size=page_size
    )
    
    total = store.count(
        event_type=event_type,
        service_name=service_name,
        incident_id=incident_id,
        healing_id=healing_id
    )
    
    return AuditListResponse(
        records=records,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/records/{record_id}", response_model=AuditRecord, tags=["audit"])
async def get_audit_record(record_id: str, request: Request):
    """Get a specific audit record."""
    store = request.app.state.audit_store
    record = store.get(record_id)
    
    if not record:
        raise HTTPException(404, "Audit record not found")
    
    return record


@router.get("/incidents/{incident_id}/timeline", tags=["timeline"])
async def get_incident_timeline(incident_id: str, request: Request):
    """Get the complete audit timeline for an incident."""
    store = request.app.state.audit_store
    
    records = store.query(incident_id=incident_id, page_size=100)
    
    # Sort by timestamp
    records.sort(key=lambda r: r.timestamp)
    
    return {
        "incident_id": incident_id,
        "events": [
            {
                "timestamp": r.timestamp.isoformat(),
                "event_type": r.event_type.value,
                "description": r.description,
                "reasoning": r.reasoning,
                "success": r.success
            }
            for r in records
        ],
        "total_events": len(records)
    }


@router.get("/healings/{healing_id}/trace", tags=["timeline"])
async def get_healing_trace(healing_id: str, request: Request):
    """Get the reasoning trace for a healing operation."""
    store = request.app.state.audit_store
    
    records = store.query(healing_id=healing_id, page_size=50)
    records.sort(key=lambda r: r.timestamp)
    
    return {
        "healing_id": healing_id,
        "trace": [
            {
                "timestamp": r.timestamp.isoformat(),
                "event_type": r.event_type.value,
                "reasoning": r.reasoning,
                "confidence": r.confidence,
                "success": r.success,
                "error": r.error_message
            }
            for r in records
        ]
    }


@router.get("/stats", tags=["stats"])
async def get_audit_stats(request: Request):
    """Get audit statistics."""
    store = request.app.state.audit_store
    
    return {
        "total_records": store.count(),
        "by_event_type": store.count_by_event_type(),
        "recent_24h": store.count_recent(hours=24),
        "success_rate": store.success_rate()
    }
