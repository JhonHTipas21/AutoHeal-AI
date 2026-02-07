"""
AutoHeal AI - AutoHeal Agent API Routes
=========================================
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
import uuid

from src.config import get_settings, HealingMode
from src.api.schemas import (
    HealingRequest,
    HealingResult,
    HealingStatus,
    HealingPlan,
    OODAState,
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
# HEALING ENDPOINTS
# =============================================================================

@router.post("/heal", response_model=HealingResult, tags=["healing"])
async def trigger_healing(
    request_data: HealingRequest,
    background_tasks: BackgroundTasks,
    request: Request
):
    """
    Trigger the OODA healing loop for an incident.
    
    This endpoint initiates the autonomous healing process:
    1. Observe: Gather context about the incident
    2. Orient: Analyze and classify the issue
    3. Decide: Generate a healing plan
    4. Act: Execute the healing actions
    """
    engine = request.app.state.ooda_engine
    
    # Check if already healing this incident
    if engine.is_healing(request_data.incident_id):
        raise HTTPException(
            status_code=409,
            detail=f"Healing already in progress for incident {request_data.incident_id}"
        )
    
    # Check concurrent healing limit
    if engine.get_active_count() >= settings.max_concurrent_healings:
        raise HTTPException(
            status_code=429,
            detail=f"Maximum concurrent healings ({settings.max_concurrent_healings}) reached"
        )
    
    # Check cooldown
    if engine.is_in_cooldown(request_data.target_service) and not request_data.force:
        raise HTTPException(
            status_code=429,
            detail=f"Service {request_data.target_service} is in cooldown period"
        )
    
    # Create healing result
    healing_id = str(uuid.uuid4())
    result = HealingResult(
        healing_id=healing_id,
        incident_id=request_data.incident_id,
        status=HealingStatus.PENDING
    )
    
    # Store the result
    engine.register_healing(result)
    
    # Run OODA loop in background
    if settings.healing_mode == HealingMode.AUTO:
        background_tasks.add_task(
            engine.run_ooda_loop,
            healing_id,
            request_data
        )
        result.status = HealingStatus.OBSERVING
    elif settings.healing_mode == HealingMode.SEMI_AUTO:
        # Generate plan but await approval
        background_tasks.add_task(
            engine.generate_plan_only,
            healing_id,
            request_data
        )
        result.status = HealingStatus.DECIDING
    else:
        # Manual mode - just analyze
        background_tasks.add_task(
            engine.analyze_only,
            healing_id,
            request_data
        )
        result.status = HealingStatus.ORIENTING
    
    logger.info(
        f"Healing triggered for incident {request_data.incident_id}",
        extra={
            "healing_id": healing_id,
            "mode": settings.healing_mode.value
        }
    )
    
    return result


@router.get("/heal/{healing_id}", response_model=HealingResult, tags=["healing"])
async def get_healing_status(healing_id: str, request: Request):
    """Get the status of a healing operation."""
    engine = request.app.state.ooda_engine
    result = engine.get_healing(healing_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Healing not found")
    
    return result


@router.get("/heal/{healing_id}/state", response_model=OODAState, tags=["healing"])
async def get_ooda_state(healing_id: str, request: Request):
    """Get the current OODA loop state for a healing operation."""
    engine = request.app.state.ooda_engine
    state = engine.get_ooda_state(healing_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="OODA state not found")
    
    return state


@router.post("/heal/{healing_id}/approve", tags=["healing"])
async def approve_healing_plan(
    healing_id: str,
    background_tasks: BackgroundTasks,
    request: Request
):
    """Approve a healing plan for execution (semi-auto mode)."""
    engine = request.app.state.ooda_engine
    result = engine.get_healing(healing_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Healing not found")
    
    if result.status != HealingStatus.DECIDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve healing in status {result.status.value}"
        )
    
    # Execute the plan
    background_tasks.add_task(engine.execute_plan, healing_id)
    
    return {"status": "approved", "healing_id": healing_id}


@router.post("/heal/{healing_id}/cancel", tags=["healing"])
async def cancel_healing(healing_id: str, request: Request):
    """Cancel a healing operation."""
    engine = request.app.state.ooda_engine
    result = engine.cancel_healing(healing_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Healing not found")
    
    return {"status": "cancelled", "healing_id": healing_id}


# =============================================================================
# HEALING HISTORY
# =============================================================================

@router.get("/history", tags=["history"])
async def get_healing_history(
    request: Request,
    service: Optional[str] = None,
    limit: int = 20
):
    """Get healing operation history."""
    engine = request.app.state.ooda_engine
    history = engine.get_history(service=service, limit=limit)
    
    return {"healings": history, "count": len(history)}


@router.get("/stats", tags=["stats"])
async def get_healing_stats(request: Request):
    """Get healing statistics."""
    engine = request.app.state.ooda_engine
    
    return {
        "active_healings": engine.get_active_count(),
        "total_healings": engine.get_total_count(),
        "success_rate": engine.get_success_rate(),
        "average_duration_seconds": engine.get_average_duration(),
        "mode": settings.healing_mode.value
    }


# =============================================================================
# CONFIGURATION
# =============================================================================

@router.get("/config", tags=["config"])
async def get_config():
    """Get current agent configuration."""
    return {
        "healing_mode": settings.healing_mode.value,
        "max_healing_attempts": settings.max_healing_attempts,
        "healing_timeout_seconds": settings.healing_timeout_seconds,
        "max_concurrent_healings": settings.max_concurrent_healings,
        "cooldown_minutes": settings.cooldown_minutes,
        "slm_provider": settings.slm_provider
    }
