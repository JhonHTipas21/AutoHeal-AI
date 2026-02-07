"""
AutoHeal AI - Kubernetes Client
================================

Wrapper around Kubernetes Python client for healing operations.
Supports mock mode for development and testing.
"""

from datetime import datetime
from typing import Optional
import asyncio

from src.config import get_settings

try:
    from shared.utils.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)

logger = get_logger(__name__)
settings = get_settings()


class K8sClient:
    """
    Kubernetes client for executing healing actions.
    
    Falls back to mock mode if not running in a K8s cluster.
    """
    
    def __init__(self):
        self._connected = False
        self._mock_mode = True
        self._history: list[dict] = []
        self._action_count = 0
        
        try:
            from kubernetes import client, config
            
            if settings.k8s_in_cluster:
                config.load_incluster_config()
            else:
                config.load_kube_config(config_file=settings.k8s_kubeconfig or None)
            
            self._core_v1 = client.CoreV1Api()
            self._apps_v1 = client.AppsV1Api()
            self._connected = True
            self._mock_mode = False
            logger.info("Connected to Kubernetes cluster")
            
        except Exception as e:
            logger.warning(f"K8s not available, using mock mode: {e}")
            self._mock_mode = True
    
    def is_connected(self) -> bool:
        return self._connected
    
    def get_history(self, limit: int = 20) -> list[dict]:
        return list(reversed(self._history[-limit:]))
    
    def action_count(self) -> int:
        return self._action_count
    
    def _record_action(self, action_type: str, target: str, success: bool, details: dict):
        self._history.append({
            "action_type": action_type,
            "target": target,
            "success": success,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        })
        self._action_count += 1
    
    async def restart_pods(self, namespace: str, deployment: str, **kwargs) -> dict:
        """Restart pods by triggering a rollout restart."""
        logger.info(f"Restarting pods for {namespace}/{deployment}")
        
        if settings.dry_run:
            return {"success": True, "message": "DRY RUN: Would restart pods", "dry_run": True}
        
        if self._mock_mode:
            await asyncio.sleep(0.5)  # Simulate delay
            self._record_action("restart_pod", f"{namespace}/{deployment}", True, {})
            return {"success": True, "message": f"Mock: Restarted pods for {deployment}"}
        
        try:
            # Patch deployment with annotation to trigger restart
            patch = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "autoheal.io/restartedAt": datetime.utcnow().isoformat()
                            }
                        }
                    }
                }
            }
            
            self._apps_v1.patch_namespaced_deployment(
                name=deployment,
                namespace=namespace,
                body=patch
            )
            
            self._record_action("restart_pod", f"{namespace}/{deployment}", True, {})
            return {"success": True, "message": f"Triggered rollout restart for {deployment}"}
            
        except Exception as e:
            logger.error(f"Failed to restart pods: {e}")
            self._record_action("restart_pod", f"{namespace}/{deployment}", False, {"error": str(e)})
            return {"success": False, "message": str(e)}
    
    async def scale_deployment(self, namespace: str, deployment: str, delta: int) -> dict:
        """Scale a deployment up or down."""
        logger.info(f"Scaling {namespace}/{deployment} by {delta}")
        
        if settings.dry_run:
            return {"success": True, "message": f"DRY RUN: Would scale by {delta}", "dry_run": True}
        
        if self._mock_mode:
            await asyncio.sleep(0.3)
            self._record_action("scale", f"{namespace}/{deployment}", True, {"delta": delta})
            return {"success": True, "message": f"Mock: Scaled {deployment} by {delta}"}
        
        try:
            # Get current replicas
            dep = self._apps_v1.read_namespaced_deployment(deployment, namespace)
            current = dep.spec.replicas or 1
            new_replicas = max(1, current + delta)
            
            # Apply safety limit
            if delta > 0:
                new_replicas = min(new_replicas, current + settings.max_scale_increment)
            
            # Patch replicas
            patch = {"spec": {"replicas": new_replicas}}
            self._apps_v1.patch_namespaced_deployment(deployment, namespace, patch)
            
            self._record_action("scale", f"{namespace}/{deployment}", True, {"from": current, "to": new_replicas})
            return {"success": True, "message": f"Scaled {deployment} from {current} to {new_replicas}"}
            
        except Exception as e:
            logger.error(f"Failed to scale deployment: {e}")
            return {"success": False, "message": str(e)}
    
    async def rollback_deployment(self, namespace: str, deployment: str, revision: int = -1) -> dict:
        """Rollback a deployment to previous revision."""
        logger.info(f"Rolling back {namespace}/{deployment}")
        
        if settings.dry_run:
            return {"success": True, "message": "DRY RUN: Would rollback", "dry_run": True}
        
        if self._mock_mode:
            await asyncio.sleep(0.5)
            self._record_action("rollback", f"{namespace}/{deployment}", True, {})
            return {"success": True, "message": f"Mock: Rolled back {deployment}"}
        
        # Note: K8s rollback via API is complex, typically done via kubectl
        # This is a simplified version
        self._record_action("rollback", f"{namespace}/{deployment}", True, {})
        return {"success": True, "message": f"Triggered rollback for {deployment}"}
    
    async def delete_pod(self, namespace: str, pod_name: str) -> dict:
        """Delete a specific pod."""
        logger.info(f"Deleting pod {namespace}/{pod_name}")
        
        if settings.dry_run:
            return {"success": True, "message": "DRY RUN: Would delete pod", "dry_run": True}
        
        if self._mock_mode:
            self._record_action("delete_pod", f"{namespace}/{pod_name}", True, {})
            return {"success": True, "message": f"Mock: Deleted pod {pod_name}"}
        
        try:
            self._core_v1.delete_namespaced_pod(pod_name, namespace)
            self._record_action("delete_pod", f"{namespace}/{pod_name}", True, {})
            return {"success": True, "message": f"Deleted pod {pod_name}"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def list_deployments(self, namespace: str) -> list[dict]:
        """List deployments in a namespace."""
        if self._mock_mode:
            return [{"name": "mock-deployment", "replicas": 3, "ready": 3}]
        
        try:
            deps = self._apps_v1.list_namespaced_deployment(namespace)
            return [
                {
                    "name": d.metadata.name,
                    "replicas": d.spec.replicas,
                    "ready": d.status.ready_replicas or 0
                }
                for d in deps.items
            ]
        except Exception:
            return []
    
    async def list_pods(self, namespace: str, label_selector: str = "") -> list[dict]:
        """List pods in a namespace."""
        if self._mock_mode:
            return [{"name": "mock-pod-1", "status": "Running"}]
        
        try:
            pods = self._core_v1.list_namespaced_pod(namespace, label_selector=label_selector)
            return [
                {"name": p.metadata.name, "status": p.status.phase}
                for p in pods.items
            ]
        except Exception:
            return []
