"""
AutoHeal AI - Action Executor
===============================

Executes healing actions via the Kubernetes Action Executor service.
"""

from typing import Optional
import httpx

from src.api.schemas import HealingAction, ActionType
from src.config import get_settings

try:
    from shared.utils.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)

logger = get_logger(__name__)
settings = get_settings()


class ActionExecutor:
    """
    Executes healing actions by dispatching to K8s executor.
    """
    
    def __init__(self, k8s_executor_url: Optional[str] = None):
        self.executor_url = (k8s_executor_url or settings.k8s_executor_url).rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.healing_timeout_seconds)
            )
        return self._client
    
    async def execute(self, action: HealingAction) -> tuple[bool, str]:
        """
        Execute a single healing action.
        
        Returns:
            Tuple of (success, message)
        """
        client = await self._get_client()
        
        try:
            payload = {
                "action_id": action.action_id,
                "action_type": action.action_type.value,
                "target": action.target,
                "parameters": action.parameters
            }
            
            response = await client.post(
                f"{self.executor_url}/api/v1/execute",
                json=payload
            )
            
            if response.status_code in (200, 201, 202):
                logger.info(
                    f"Action executed successfully: {action.action_type.value}",
                    extra={"action_id": action.action_id}
                )
                return True, "Action completed successfully"
            else:
                return False, f"Executor returned status {response.status_code}"
                
        except httpx.TimeoutException:
            return False, "Action execution timed out"
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return False, str(e)
    
    async def execute_batch(
        self,
        actions: list[HealingAction]
    ) -> dict:
        """
        Execute a batch of actions.
        
        Returns:
            Dictionary with results summary
        """
        results = {
            "total": len(actions),
            "successful": 0,
            "failed": 0,
            "details": []
        }
        
        for action in actions:
            success, message = await self.execute(action)
            
            results["details"].append({
                "action_id": action.action_id,
                "action_type": action.action_type.value,
                "success": success,
                "message": message
            })
            
            if success:
                results["successful"] += 1
            else:
                results["failed"] += 1
        
        return results
    
    async def validate_action(self, action: HealingAction) -> tuple[bool, str]:
        """
        Validate an action before execution.
        
        Returns:
            Tuple of (valid, message)
        """
        # Check action type is supported
        supported = {t for t in ActionType}
        if action.action_type not in supported:
            return False, f"Unsupported action type: {action.action_type}"
        
        # Check target is specified
        if not action.target:
            return False, "Action target not specified"
        
        # Check required parameters
        if action.action_type == ActionType.SCALE_UP:
            if "increment" not in action.parameters:
                return False, "SCALE_UP requires 'increment' parameter"
        
        return True, "Action is valid"
    
    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
