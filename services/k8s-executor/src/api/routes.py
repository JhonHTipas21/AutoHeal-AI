"""
AutoHeal AI - K8s Executor API Routes
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, Request

from src.api.schemas import ExecuteRequest, ExecuteResponse, ActionStatus, ActionType
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


@router.post("/execute", response_model=ExecuteResponse, tags=["execute"])
async def execute_action(req: ExecuteRequest, request: Request):
    """Execute a Kubernetes healing action."""
    k8s = request.app.state.k8s_client
    
    logger.info(
        f"Executing action: {req.action_type.value}",
        extra={"action_id": req.action_id, "target": req.target}
    )
    
    try:
        # Parse target (namespace/resource)
        parts = req.target.split("/")
        namespace = parts[0] if len(parts) > 1 else settings.k8s_namespace
        resource = parts[-1]
        
        # Execute based on action type
        if req.action_type == ActionType.RESTART_POD:
            result = await k8s.restart_pods(namespace, resource, **req.parameters)
        elif req.action_type == ActionType.SCALE_UP:
            increment = req.parameters.get("increment", 1)
            result = await k8s.scale_deployment(namespace, resource, increment)
        elif req.action_type == ActionType.SCALE_DOWN:
            decrement = req.parameters.get("decrement", 1)
            result = await k8s.scale_deployment(namespace, resource, -decrement)
        elif req.action_type == ActionType.ROLLBACK:
            revision = req.parameters.get("revision", -1)
            result = await k8s.rollback_deployment(namespace, resource, revision)
        elif req.action_type == ActionType.DELETE_POD:
            result = await k8s.delete_pod(namespace, resource)
        else:
            raise HTTPException(400, f"Unsupported action: {req.action_type}")
        
        return ExecuteResponse(
            action_id=req.action_id,
            status=ActionStatus.COMPLETED if result["success"] else ActionStatus.FAILED,
            message=result.get("message", "Action executed"),
            dry_run=settings.dry_run,
            details=result
        )
        
    except Exception as e:
        logger.error(f"Action execution failed: {e}")
        return ExecuteResponse(
            action_id=req.action_id,
            status=ActionStatus.FAILED,
            message=str(e),
            dry_run=settings.dry_run
        )


@router.get("/actions", tags=["history"])
async def list_actions(request: Request, limit: int = 20):
    """List recent action history."""
    k8s = request.app.state.k8s_client
    return {"actions": k8s.get_history(limit), "count": k8s.action_count()}


@router.get("/deployments/{namespace}", tags=["resources"])
async def list_deployments(namespace: str, request: Request):
    """List deployments in a namespace."""
    k8s = request.app.state.k8s_client
    deployments = await k8s.list_deployments(namespace)
    return {"namespace": namespace, "deployments": deployments}


@router.get("/pods/{namespace}", tags=["resources"])
async def list_pods(namespace: str, request: Request, label_selector: str = ""):
    """List pods in a namespace."""
    k8s = request.app.state.k8s_client
    pods = await k8s.list_pods(namespace, label_selector)
    return {"namespace": namespace, "pods": pods}
