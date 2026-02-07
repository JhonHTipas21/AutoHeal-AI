"""
AutoHeal AI - OODA Engine
===========================

The core reasoning loop for autonomous healing.

OODA (Observe, Orient, Decide, Act) is a decision-making framework
used for intelligent, context-aware healing decisions.

Phases:
1. OBSERVE: Gather context about the incident
   - Current metrics
   - Recent logs
   - Historical incidents
   - Service topology

2. ORIENT: Analyze and classify
   - Correlate with known patterns
   - Assess severity and impact
   - Consider dependencies

3. DECIDE: Generate healing plan
   - Select appropriate actions
   - Prioritize by risk and effectiveness
   - Validate against safety constraints

4. ACT: Execute healing
   - Send actions to K8s executor
   - Monitor progress
   - Validate results
"""

from datetime import datetime, timedelta
from typing import Optional
from threading import Lock
import uuid
import httpx

from src.api.schemas import (
    HealingRequest,
    HealingResult,
    HealingStatus,
    HealingPlan,
    HealingAction,
    ActionType,
    OODAState,
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


class OODAEngine:
    """
    The OODA reasoning engine for autonomous healing.
    
    Manages the complete lifecycle of healing operations,
    from observation to validation.
    """
    
    def __init__(self):
        self._healings: dict[str, HealingResult] = {}
        self._states: dict[str, OODAState] = {}
        self._cooldowns: dict[str, datetime] = {}
        self._lock = Lock()
        self._history: list[HealingResult] = []
    
    def register_healing(self, result: HealingResult) -> None:
        """Register a new healing operation."""
        with self._lock:
            self._healings[result.healing_id] = result
            self._states[result.healing_id] = OODAState(
                healing_id=result.healing_id,
                phase="pending"
            )
    
    def get_healing(self, healing_id: str) -> Optional[HealingResult]:
        """Get a healing result."""
        return self._healings.get(healing_id)
    
    def get_ooda_state(self, healing_id: str) -> Optional[OODAState]:
        """Get the OODA state for a healing."""
        return self._states.get(healing_id)
    
    def is_healing(self, incident_id: str) -> bool:
        """Check if an incident is being healed."""
        return any(
            h.incident_id == incident_id
            and h.status not in (HealingStatus.COMPLETED, HealingStatus.FAILED, HealingStatus.CANCELLED)
            for h in self._healings.values()
        )
    
    def is_in_cooldown(self, service: str) -> bool:
        """Check if a service is in cooldown."""
        if service not in self._cooldowns:
            return False
        
        cooldown_until = self._cooldowns[service]
        return datetime.utcnow() < cooldown_until
    
    def get_active_count(self) -> int:
        """Get count of active healings."""
        return sum(
            1 for h in self._healings.values()
            if h.status not in (HealingStatus.COMPLETED, HealingStatus.FAILED, HealingStatus.CANCELLED)
        )
    
    def get_total_count(self) -> int:
        """Get total healing count."""
        return len(self._healings) + len(self._history)
    
    def get_success_rate(self) -> float:
        """Calculate healing success rate."""
        completed = [h for h in self._history if h.status == HealingStatus.COMPLETED]
        total = len(self._history)
        return len(completed) / total if total > 0 else 0.0
    
    def get_average_duration(self) -> float:
        """Calculate average healing duration."""
        durations = []
        for h in self._history:
            if h.completed_at and h.started_at:
                duration = (h.completed_at - h.started_at).total_seconds()
                durations.append(duration)
        return sum(durations) / len(durations) if durations else 0.0
    
    def get_history(
        self,
        service: Optional[str] = None,
        limit: int = 20
    ) -> list[HealingResult]:
        """Get healing history."""
        history = list(self._history)
        
        # Add completed healings from current dict
        for h in self._healings.values():
            if h.status in (HealingStatus.COMPLETED, HealingStatus.FAILED):
                history.append(h)
        
        # Filter by service if specified
        if service:
            # Note: Need to track service in result
            pass
        
        # Sort by started_at descending
        history.sort(key=lambda h: h.started_at, reverse=True)
        
        return history[:limit]
    
    async def run_ooda_loop(
        self,
        healing_id: str,
        request: HealingRequest
    ) -> None:
        """
        Run the complete OODA loop.
        
        This is the main autonomous healing workflow.
        """
        result = self._healings.get(healing_id)
        state = self._states.get(healing_id)
        
        if not result or not state:
            return
        
        try:
            # Phase 1: OBSERVE
            state.phase = "observe"
            result.status = HealingStatus.OBSERVING
            observation = await self._observe(request)
            state.observation = observation
            
            # Phase 2: ORIENT
            state.phase = "orient"
            result.status = HealingStatus.ORIENTING
            orientation = await self._orient(request, observation)
            state.orientation = orientation
            
            # Phase 3: DECIDE
            state.phase = "decide"
            result.status = HealingStatus.DECIDING
            plan = await self._decide(request, observation, orientation)
            result.plan = plan
            state.decision = plan.decision
            
            # Phase 4: ACT
            state.phase = "act"
            result.status = HealingStatus.ACTING
            await self._act(healing_id, plan)
            
            # Phase 5: VALIDATE
            state.phase = "validate"
            result.status = HealingStatus.VALIDATING
            success = await self._validate(request.target_service)
            
            # Complete
            result.status = HealingStatus.COMPLETED if success else HealingStatus.FAILED
            result.completed_at = datetime.utcnow()
            result.result_message = "Healing completed successfully" if success else "Healing validation failed"
            
            # Set cooldown
            self._cooldowns[request.target_service] = datetime.utcnow() + timedelta(minutes=settings.cooldown_minutes)
            
            logger.info(
                f"OODA loop completed for healing {healing_id}",
                extra={"status": result.status.value}
            )
            
        except Exception as e:
            logger.error(f"OODA loop failed: {e}", exc_info=True)
            result.status = HealingStatus.FAILED
            result.error_message = str(e)
            result.completed_at = datetime.utcnow()
    
    async def generate_plan_only(
        self,
        healing_id: str,
        request: HealingRequest
    ) -> None:
        """Generate healing plan without execution."""
        result = self._healings.get(healing_id)
        state = self._states.get(healing_id)
        
        if not result or not state:
            return
        
        try:
            # Run O-O-D phases
            state.phase = "observe"
            observation = await self._observe(request)
            state.observation = observation
            
            state.phase = "orient"
            orientation = await self._orient(request, observation)
            state.orientation = orientation
            
            state.phase = "decide"
            plan = await self._decide(request, observation, orientation)
            result.plan = plan
            state.decision = plan.decision
            
            # Await approval
            result.status = HealingStatus.DECIDING
            result.result_message = "Plan generated, awaiting approval"
            
        except Exception as e:
            logger.error(f"Plan generation failed: {e}")
            result.status = HealingStatus.FAILED
            result.error_message = str(e)
    
    async def analyze_only(
        self,
        healing_id: str,
        request: HealingRequest
    ) -> None:
        """Analyze only, no action (manual mode)."""
        result = self._healings.get(healing_id)
        state = self._states.get(healing_id)
        
        if not result or not state:
            return
        
        try:
            state.phase = "observe"
            observation = await self._observe(request)
            state.observation = observation
            
            state.phase = "orient"
            orientation = await self._orient(request, observation)
            state.orientation = orientation
            
            result.status = HealingStatus.COMPLETED
            result.result_message = "Analysis complete. Manual action required."
            result.completed_at = datetime.utcnow()
            
        except Exception as e:
            result.status = HealingStatus.FAILED
            result.error_message = str(e)
    
    async def execute_plan(self, healing_id: str) -> None:
        """Execute a previously generated plan."""
        result = self._healings.get(healing_id)
        
        if not result or not result.plan:
            return
        
        try:
            result.status = HealingStatus.ACTING
            await self._act(healing_id, result.plan)
            
            result.status = HealingStatus.VALIDATING
            # Validation would go here
            
            result.status = HealingStatus.COMPLETED
            result.completed_at = datetime.utcnow()
            result.result_message = "Plan executed successfully"
            
        except Exception as e:
            result.status = HealingStatus.FAILED
            result.error_message = str(e)
    
    def cancel_healing(self, healing_id: str) -> Optional[HealingResult]:
        """Cancel a healing operation."""
        result = self._healings.get(healing_id)
        if result:
            result.status = HealingStatus.CANCELLED
            result.completed_at = datetime.utcnow()
        return result
    
    # -------------------------------------------------------------------------
    # OODA Phase Implementations
    # -------------------------------------------------------------------------
    
    async def _observe(self, request: HealingRequest) -> str:
        """
        OBSERVE phase: Gather context about the incident.
        """
        observations = []
        
        observations.append(f"Incident {request.incident_id} affecting {request.target_service}")
        observations.append(f"Severity: {request.severity}")
        
        if request.root_cause:
            observations.append(f"Suspected root cause: {request.root_cause}")
        
        if request.recommended_actions:
            observations.append(f"Recommended actions: {', '.join(request.recommended_actions)}")
        
        # In production, would fetch:
        # - Current metrics from monitoring service
        # - Recent logs from log-intelligence
        # - Service topology from K8s
        
        observation = " | ".join(observations)
        logger.info(f"OBSERVE: {observation}")
        
        return observation
    
    async def _orient(self, request: HealingRequest, observation: str) -> str:
        """
        ORIENT phase: Analyze and classify the issue.
        """
        # Use decision maker for analysis
        from src.core.decision_maker import DecisionMaker
        maker = DecisionMaker()
        
        orientation = maker.analyze_incident(
            root_cause=request.root_cause,
            severity=request.severity,
            recommended_actions=request.recommended_actions
        )
        
        logger.info(f"ORIENT: {orientation}")
        
        return orientation
    
    async def _decide(
        self,
        request: HealingRequest,
        observation: str,
        orientation: str
    ) -> HealingPlan:
        """
        DECIDE phase: Generate healing plan.
        """
        from src.core.decision_maker import DecisionMaker
        maker = DecisionMaker()
        
        plan = maker.generate_plan(
            incident_id=request.incident_id,
            service=request.target_service,
            namespace=request.target_namespace,
            observation=observation,
            orientation=orientation,
            recommended_actions=request.recommended_actions
        )
        
        logger.info(f"DECIDE: Generated plan with {len(plan.actions)} actions")
        
        return plan
    
    async def _act(self, healing_id: str, plan: HealingPlan) -> None:
        """
        ACT phase: Execute healing actions.
        """
        result = self._healings.get(healing_id)
        if not result:
            return
        
        for action in plan.actions:
            try:
                success = await self._execute_action(action)
                result.actions_executed += 1
                if success:
                    result.actions_successful += 1
                
                logger.info(
                    f"Action {action.action_type.value} {'succeeded' if success else 'failed'}",
                    extra={"action_id": action.action_id}
                )
                
            except Exception as e:
                logger.error(f"Action execution failed: {e}")
                result.actions_executed += 1
    
    async def _execute_action(self, action: HealingAction) -> bool:
        """Execute a single healing action via K8s executor."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{settings.k8s_executor_url}/api/v1/execute",
                    json={
                        "action_id": action.action_id,
                        "action_type": action.action_type.value,
                        "target": action.target,
                        "parameters": action.parameters
                    }
                )
                
                return response.status_code in (200, 201, 202)
                
        except Exception as e:
            logger.error(f"Failed to execute action: {e}")
            return False
    
    async def _validate(self, service: str) -> bool:
        """
        Validate that healing was successful.
        
        In production, would check:
        - Service health endpoint
        - Error rates
        - Latency
        """
        # For now, assume success
        return True
