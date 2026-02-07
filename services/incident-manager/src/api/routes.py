"""
AutoHeal AI - Incident Manager API Routes
==========================================
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Query
import uuid

from src.config import get_settings
from src.api.schemas import (
    AnomalyEventInput,
    LogAnalysisEventInput,
    Incident,
    IncidentListResponse,
    IncidentStatus,
    IncidentSeverity,
    TriggerHealingRequest,
)

try:
    from shared.utils.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter()


# =============================================================================
# EVENT INGESTION
# =============================================================================

@router.post("/events/anomaly", status_code=202, tags=["events"])
async def receive_anomaly_event(event: AnomalyEventInput, request: Request):
    """
    Receive an anomaly event from the monitoring service.
    
    Creates or updates an incident based on the event.
    """
    store = request.app.state.incident_store
    
    # Check for existing incident to correlate
    existing = store.find_related_incident(
        service=event.target_service,
        namespace=event.target_namespace,
        window_minutes=settings.incident_correlation_window_minutes
    )
    
    if existing:
        # Add event to existing incident
        store.add_event_to_incident(existing.incident_id, event.event_id)
        logger.info(
            f"Added event to existing incident {existing.incident_id}",
            extra={"event_id": event.event_id, "incident_id": existing.incident_id}
        )
        return {"action": "correlated", "incident_id": existing.incident_id}
    
    # Create new incident
    severity = IncidentSeverity(event.severity) if event.severity in IncidentSeverity.__members__.values() else IncidentSeverity.MEDIUM
    
    incident = Incident(
        incident_id=str(uuid.uuid4()),
        title=f"{event.anomaly_type.replace('_', ' ').title()} on {event.target_service}",
        description=f"Detected {event.anomaly_type}: {event.metric_name} = {event.current_value} (threshold: {event.threshold_value})",
        status=IncidentStatus.NEW,
        severity=severity,
        target_service=event.target_service,
        target_namespace=event.target_namespace,
        event_ids=[event.event_id],
        event_count=1,
        root_cause=f"Possible cause: {event.anomaly_type}",
        confidence=0.7
    )
    
    store.create_incident(incident)
    
    logger.info(
        f"Created new incident {incident.incident_id}",
        extra={"incident_id": incident.incident_id, "service": event.target_service}
    )
    
    # Trigger healing if enabled
    if settings.healing_enabled and not settings.approval_required:
        await _trigger_healing(incident)
    
    return {"action": "created", "incident_id": incident.incident_id}


@router.post("/events/log-analysis", status_code=202, tags=["events"])
async def receive_log_analysis_event(event: LogAnalysisEventInput, request: Request):
    """
    Receive a log analysis event from the log intelligence service.
    """
    store = request.app.state.incident_store
    
    # Check for existing incident
    existing = store.find_related_incident(
        service=event.service_name,
        namespace=event.namespace,
        window_minutes=settings.incident_correlation_window_minutes
    )
    
    if existing:
        store.add_event_to_incident(existing.incident_id, event.event_id)
        # Update with log analysis context
        store.update_incident(existing.incident_id, {
            "root_cause": event.root_cause,
            "confidence": event.confidence,
            "healing_actions": event.recommended_actions
        })
        return {"action": "correlated", "incident_id": existing.incident_id}
    
    # Create new incident
    severity = IncidentSeverity(event.severity) if event.severity in IncidentSeverity.__members__.values() else IncidentSeverity.MEDIUM
    
    incident = Incident(
        incident_id=str(uuid.uuid4()),
        title=f"{event.error_category.replace('_', ' ').title()} Error in {event.service_name}",
        description=event.sample_message[:500],
        status=IncidentStatus.ANALYZING,
        severity=severity,
        target_service=event.service_name,
        target_namespace=event.namespace,
        event_ids=[event.event_id],
        event_count=event.error_count,
        root_cause=event.root_cause,
        confidence=event.confidence,
        healing_actions=event.recommended_actions
    )
    
    store.create_incident(incident)
    
    logger.info(f"Created incident from log analysis: {incident.incident_id}")
    
    if settings.healing_enabled and not settings.approval_required:
        await _trigger_healing(incident)
    
    return {"action": "created", "incident_id": incident.incident_id}


# =============================================================================
# INCIDENT MANAGEMENT
# =============================================================================

@router.get("/incidents", response_model=IncidentListResponse, tags=["incidents"])
async def list_incidents(
    request: Request,
    status: Optional[IncidentStatus] = None,
    severity: Optional[IncidentSeverity] = None,
    service: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100)
):
    """List incidents with optional filtering."""
    store = request.app.state.incident_store
    
    incidents = store.list_incidents(
        status=status,
        severity=severity,
        service=service,
        page=page,
        page_size=page_size
    )
    
    total = store.count_incidents(status=status, severity=severity, service=service)
    
    return IncidentListResponse(
        incidents=incidents,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/incidents/{incident_id}", response_model=Incident, tags=["incidents"])
async def get_incident(incident_id: str, request: Request):
    """Get a specific incident by ID."""
    store = request.app.state.incident_store
    incident = store.get_incident(incident_id)
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    return incident


@router.patch("/incidents/{incident_id}", tags=["incidents"])
async def update_incident(
    incident_id: str,
    status: Optional[IncidentStatus] = None,
    severity: Optional[IncidentSeverity] = None,
    request: Request = None
):
    """Update incident status or severity."""
    store = request.app.state.incident_store
    
    updates = {}
    if status:
        updates["status"] = status
        if status == IncidentStatus.RESOLVED:
            updates["resolved_at"] = datetime.utcnow()
    if severity:
        updates["severity"] = severity
    
    incident = store.update_incident(incident_id, updates)
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    return incident


@router.delete("/incidents/{incident_id}", tags=["incidents"])
async def close_incident(incident_id: str, request: Request):
    """Close/resolve an incident."""
    store = request.app.state.incident_store
    
    incident = store.update_incident(incident_id, {
        "status": IncidentStatus.RESOLVED,
        "resolved_at": datetime.utcnow()
    })
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    return {"status": "closed", "incident_id": incident_id}


# =============================================================================
# HEALING
# =============================================================================

@router.post("/incidents/{incident_id}/heal", tags=["healing"])
async def trigger_incident_healing(incident_id: str, request: Request):
    """Manually trigger healing for an incident."""
    store = request.app.state.incident_store
    incident = store.get_incident(incident_id)
    
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    if incident.status == IncidentStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="Incident already resolved")
    
    result = await _trigger_healing(incident)
    
    return {"status": "healing_triggered", "incident_id": incident_id, "result": result}


async def _trigger_healing(incident: Incident) -> dict:
    """Internal function to trigger healing via AutoHeal Agent."""
    import httpx
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.autoheal_agent_url}/api/v1/heal",
                json={
                    "incident_id": incident.incident_id,
                    "target_service": incident.target_service,
                    "target_namespace": incident.target_namespace,
                    "severity": incident.severity.value,
                    "root_cause": incident.root_cause,
                    "recommended_actions": incident.healing_actions
                }
            )
            
            if response.status_code in (200, 201, 202):
                logger.info(f"Triggered healing for incident {incident.incident_id}")
                return {"triggered": True, "response": response.json()}
            else:
                logger.warning(f"Failed to trigger healing: {response.status_code}")
                return {"triggered": False, "error": response.text}
                
    except Exception as e:
        logger.error(f"Error triggering healing: {e}")
        return {"triggered": False, "error": str(e)}


# =============================================================================
# STATISTICS
# =============================================================================

@router.get("/stats", tags=["stats"])
async def get_incident_stats(request: Request):
    """Get incident statistics."""
    store = request.app.state.incident_store
    
    return {
        "total_incidents": store.count_incidents(),
        "active_incidents": store.count_active(),
        "by_status": store.count_by_status(),
        "by_severity": store.count_by_severity(),
        "last_24h": store.count_recent(hours=24)
    }
