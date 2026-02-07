"""
AutoHeal AI - Decision Maker
==============================

Generates healing plans based on incident analysis.
Uses pattern matching and heuristics for decision making.
"""

from __future__ import annotations

from datetime import datetime
import uuid

from src.api.schemas import HealingPlan, HealingAction, ActionType

try:
    from shared.utils.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)

logger = get_logger(__name__)


class DecisionMaker:
    """
    Generates healing decisions and plans.
    
    Uses a rule-based system with pattern matching
    to select appropriate actions for different incident types.
    """
    
    # Action mappings for different root causes
    CAUSE_ACTION_MAP = {
        "error_rate_spike": [
            (ActionType.RESTART_POD, "Restart problematic pods to clear state"),
            (ActionType.SCALE_UP, "Scale up to handle load if needed"),
        ],
        "latency_spike": [
            (ActionType.SCALE_UP, "Scale up to reduce load per instance"),
            (ActionType.CIRCUIT_BREAKER, "Enable circuit breaker for slow dependencies"),
        ],
        "cpu_overload": [
            (ActionType.SCALE_UP, "Add more replicas to distribute load"),
            (ActionType.INCREASE_RESOURCES, "Increase CPU limits if scaling not possible"),
        ],
        "memory_overload": [
            (ActionType.RESTART_POD, "Restart pods to clear memory"),
            (ActionType.INCREASE_RESOURCES, "Increase memory limits"),
        ],
        "pod_crash_loop": [
            (ActionType.ROLLBACK, "Rollback to previous stable version"),
            (ActionType.RESTART_POD, "Restart with fresh state"),
        ],
        "connection_error": [
            (ActionType.CIRCUIT_BREAKER, "Enable circuit breaker"),
            (ActionType.FAILOVER, "Failover to healthy instances"),
        ],
        "timeout": [
            (ActionType.SCALE_UP, "Add capacity to reduce latency"),
            (ActionType.RATE_LIMIT, "Apply rate limiting to prevent overload"),
        ],
        "out_of_memory": [
            (ActionType.RESTART_POD, "Restart to clear memory state"),
            (ActionType.INCREASE_RESOURCES, "Increase memory allocation"),
        ],
        "database": [
            (ActionType.RESTART_POD, "Restart to reset connections"),
            (ActionType.FAILOVER, "Failover to replica if available"),
        ],
    }
    
    def analyze_incident(
        self,
        root_cause: str | None,
        severity: str,
        recommended_actions: list[str]
    ) -> str:
        """
        Analyze an incident and generate orientation context.
        
        Returns a summary of the analysis.
        """
        analysis_parts = []
        
        if root_cause:
            analysis_parts.append(f"Root cause identified: {root_cause}")
            
            # Match to known patterns
            normalized = root_cause.lower().replace(" ", "_").replace("-", "_")
            if any(pattern in normalized for pattern in self.CAUSE_ACTION_MAP.keys()):
                analysis_parts.append("Known pattern detected - automated healing available")
            else:
                analysis_parts.append("Unknown pattern - conservative approach recommended")
        else:
            analysis_parts.append("No root cause identified - will attempt general recovery")
        
        # Severity analysis
        if severity in ("critical", "high"):
            analysis_parts.append(f"{severity.upper()} severity - immediate action required")
        else:
            analysis_parts.append(f"{severity.title()} severity - standard remediation")
        
        # Recommended actions
        if recommended_actions:
            analysis_parts.append(f"Recommendations available: {len(recommended_actions)} actions")
        
        return " | ".join(analysis_parts)
    
    def generate_plan(
        self,
        incident_id: str,
        service: str,
        namespace: str,
        observation: str,
        orientation: str,
        recommended_actions: list[str]
    ) -> HealingPlan:
        """
        Generate a healing plan based on analysis.
        
        Returns a HealingPlan with prioritized actions.
        """
        plan_id = str(uuid.uuid4())
        actions = []
        
        # Determine actions based on observation
        action_types = self._select_actions(observation, recommended_actions)
        
        for action_type, reasoning in action_types:
            action = HealingAction(
                action_id=str(uuid.uuid4()),
                action_type=action_type,
                target=f"{namespace}/{service}",
                parameters=self._get_action_parameters(action_type, service, namespace),
                reasoning=reasoning,
                risk_level=self._assess_action_risk(action_type),
                reversible=action_type != ActionType.CUSTOM
            )
            actions.append(action)
        
        # If no specific actions matched, use safe defaults
        if not actions:
            actions.append(HealingAction(
                action_id=str(uuid.uuid4()),
                action_type=ActionType.RESTART_POD,
                target=f"{namespace}/{service}",
                parameters={"replicas": 1, "strategy": "rolling"},
                reasoning="Default recovery action - restart pods with rolling update",
                risk_level="low",
                reversible=True
            ))
        
        # Calculate confidence
        confidence = self._calculate_confidence(actions, observation)
        
        plan = HealingPlan(
            plan_id=plan_id,
            incident_id=incident_id,
            observation=observation,
            orientation=orientation,
            decision=f"Execute {len(actions)} healing actions for {service}",
            actions=actions,
            estimated_duration_seconds=len(actions) * 30,
            confidence=confidence,
            risk_assessment=self._assess_plan_risk(actions)
        )
        
        logger.info(
            f"Generated healing plan {plan_id}",
            extra={
                "actions": len(actions),
                "confidence": confidence
            }
        )
        
        return plan
    
    def _select_actions(
        self,
        observation: str,
        recommended_actions: list[str]
    ) -> list[tuple[ActionType, str]]:
        """Select appropriate actions based on observation."""
        selected = []
        observation_lower = observation.lower()
        
        # Check against known patterns
        for pattern, actions in self.CAUSE_ACTION_MAP.items():
            if pattern.replace("_", " ") in observation_lower or pattern in observation_lower:
                selected.extend(actions[:2])  # Take up to 2 actions
                break
        
        # Parse recommended actions from log analysis
        for rec in recommended_actions[:2]:
            rec_lower = rec.lower()
            
            if "restart" in rec_lower:
                selected.append((ActionType.RESTART_POD, rec))
            elif "scale" in rec_lower:
                selected.append((ActionType.SCALE_UP, rec))
            elif "rollback" in rec_lower:
                selected.append((ActionType.ROLLBACK, rec))
            elif "circuit" in rec_lower:
                selected.append((ActionType.CIRCUIT_BREAKER, rec))
        
        # Deduplicate
        seen = set()
        unique = []
        for action_type, reasoning in selected:
            if action_type not in seen:
                seen.add(action_type)
                unique.append((action_type, reasoning))
        
        return unique[:3]  # Max 3 actions
    
    def _get_action_parameters(
        self,
        action_type: ActionType,
        service: str,
        namespace: str
    ) -> dict:
        """Get default parameters for an action type."""
        params = {
            "service": service,
            "namespace": namespace,
        }
        
        if action_type == ActionType.RESTART_POD:
            params.update({
                "strategy": "rolling",
                "max_unavailable": 1
            })
        elif action_type == ActionType.SCALE_UP:
            params.update({
                "increment": 1,
                "max_replicas": 10
            })
        elif action_type == ActionType.ROLLBACK:
            params.update({
                "revision": -1  # Previous revision
            })
        elif action_type == ActionType.INCREASE_RESOURCES:
            params.update({
                "cpu_multiplier": 1.5,
                "memory_multiplier": 1.5
            })
        
        return params
    
    def _assess_action_risk(self, action_type: ActionType) -> str:
        """Assess risk level for an action."""
        high_risk = {ActionType.ROLLBACK, ActionType.SCALE_DOWN, ActionType.CUSTOM}
        medium_risk = {ActionType.INCREASE_RESOURCES, ActionType.FAILOVER}
        
        if action_type in high_risk:
            return "high"
        elif action_type in medium_risk:
            return "medium"
        else:
            return "low"
    
    def _assess_plan_risk(self, actions: list[HealingAction]) -> str:
        """Assess overall risk of a plan."""
        risks = [a.risk_level for a in actions]
        
        if "high" in risks:
            return "HIGH: Plan contains high-risk actions. Manual review recommended."
        elif "medium" in risks:
            return "MEDIUM: Plan contains moderately risky actions. Monitor closely."
        else:
            return "LOW: Plan contains low-risk, reversible actions."
    
    def _calculate_confidence(
        self,
        actions: list[HealingAction],
        observation: str
    ) -> float:
        """Calculate confidence in the healing plan."""
        base_confidence = 0.7
        
        # Increase for known patterns
        if "known pattern" in observation.lower():
            base_confidence += 0.15
        
        # Decrease for unknown patterns
        if "unknown pattern" in observation.lower():
            base_confidence -= 0.2
        
        # Adjust for risk
        if any(a.risk_level == "high" for a in actions):
            base_confidence -= 0.1
        
        return max(0.3, min(0.95, base_confidence))
