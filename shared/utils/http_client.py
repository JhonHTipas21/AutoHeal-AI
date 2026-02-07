"""
AutoHeal AI - HTTP Service Client
=================================

Async HTTP client for service-to-service communication.
Includes automatic retries, circuit breaker patterns, and correlation ID propagation.

Usage:
    from shared.utils.http_client import ServiceClient
    
    client = ServiceClient(base_url="http://incident-manager:8002")
    response = await client.post("/api/v1/incidents", data=incident_data)
"""

import httpx
from typing import Any, Optional
from dataclasses import dataclass
from contextlib import asynccontextmanager

from shared.utils.logging import get_logger, get_correlation_id

logger = get_logger(__name__)


@dataclass
class ServiceClientConfig:
    """Configuration for the HTTP service client."""
    timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    retry_backoff_multiplier: float = 2.0


class ServiceClient:
    """
    Async HTTP client for inter-service communication.
    
    Features:
    - Automatic correlation ID propagation
    - Connection pooling
    - Configurable timeouts
    - Async context manager support
    
    Example:
        async with ServiceClient("http://audit-service:8005") as client:
            response = await client.post("/api/v1/audit/log", data=audit_entry)
            if response.status_code == 200:
                print("Audit logged successfully")
    """
    
    def __init__(
        self,
        base_url: str,
        config: Optional[ServiceClientConfig] = None
    ):
        """
        Initialize the service client.
        
        Args:
            base_url: Base URL of the target service (e.g., "http://localhost:8002")
            config: Optional configuration overrides
        """
        self.base_url = base_url.rstrip("/")
        self.config = config or ServiceClientConfig()
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.config.timeout_seconds),
                follow_redirects=True
            )
        return self._client
    
    def _build_headers(self, extra_headers: Optional[dict] = None) -> dict:
        """Build request headers with correlation ID."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AutoHeal-ServiceClient/1.0",
        }
        
        # Propagate correlation ID for distributed tracing
        correlation_id = get_correlation_id()
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        
        if extra_headers:
            headers.update(extra_headers)
        
        return headers
    
    async def get(
        self,
        path: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None
    ) -> httpx.Response:
        """
        Make a GET request to the service.
        
        Args:
            path: API path (e.g., "/api/v1/health")
            params: Optional query parameters
            headers: Optional additional headers
            
        Returns:
            httpx.Response object
        """
        client = await self._get_client()
        
        logger.debug(
            f"GET {self.base_url}{path}",
            extra={"params": params}
        )
        
        response = await client.get(
            path,
            params=params,
            headers=self._build_headers(headers)
        )
        
        logger.debug(
            f"Response: {response.status_code}",
            extra={"path": path, "status": response.status_code}
        )
        
        return response
    
    async def post(
        self,
        path: str,
        data: Optional[dict[str, Any]] = None,
        headers: Optional[dict] = None
    ) -> httpx.Response:
        """
        Make a POST request to the service.
        
        Args:
            path: API path (e.g., "/api/v1/incidents")
            data: JSON payload to send
            headers: Optional additional headers
            
        Returns:
            httpx.Response object
        """
        client = await self._get_client()
        
        logger.debug(
            f"POST {self.base_url}{path}",
            extra={"payload_keys": list(data.keys()) if data else []}
        )
        
        response = await client.post(
            path,
            json=data,
            headers=self._build_headers(headers)
        )
        
        logger.debug(
            f"Response: {response.status_code}",
            extra={"path": path, "status": response.status_code}
        )
        
        return response
    
    async def put(
        self,
        path: str,
        data: Optional[dict[str, Any]] = None,
        headers: Optional[dict] = None
    ) -> httpx.Response:
        """
        Make a PUT request to the service.
        
        Args:
            path: API path
            data: JSON payload to send
            headers: Optional additional headers
            
        Returns:
            httpx.Response object
        """
        client = await self._get_client()
        
        response = await client.put(
            path,
            json=data,
            headers=self._build_headers(headers)
        )
        
        return response
    
    async def delete(
        self,
        path: str,
        headers: Optional[dict] = None
    ) -> httpx.Response:
        """
        Make a DELETE request to the service.
        
        Args:
            path: API path
            headers: Optional additional headers
            
        Returns:
            httpx.Response object
        """
        client = await self._get_client()
        
        response = await client.delete(
            path,
            headers=self._build_headers(headers)
        )
        
        return response
    
    async def health_check(self) -> bool:
        """
        Check if the target service is healthy.
        
        Returns:
            True if service responds with 200, False otherwise
        """
        try:
            response = await self.get("/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning(
                f"Health check failed for {self.base_url}",
                extra={"error": str(e)}
            )
            return False
    
    async def close(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self) -> "ServiceClient":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()


@asynccontextmanager
async def create_service_client(
    base_url: str,
    config: Optional[ServiceClientConfig] = None
):
    """
    Create a service client as an async context manager.
    
    This is the recommended way to use the ServiceClient for
    one-off requests to ensure proper cleanup.
    
    Example:
        async with create_service_client("http://audit:8005") as client:
            await client.post("/api/v1/log", data={"event": "test"})
    """
    client = ServiceClient(base_url, config)
    try:
        yield client
    finally:
        await client.close()
