"""
AutoHeal AI - Log Fetcher
===========================

Fetches logs from Loki for analysis.
Supports LogQL queries for filtering by service, namespace, time range.
"""

from datetime import datetime, timedelta
from typing import Optional
import httpx

from src.api.schemas import LogEntry, LogLevel
from src.core.log_parser import LogParser
from src.config import get_settings

try:
    from shared.utils.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)

logger = get_logger(__name__)
settings = get_settings()


class LogFetcher:
    """
    Fetches logs from Loki using LogQL.
    
    Provides filtering by:
    - Service name
    - Kubernetes namespace
    - Time range
    - Log level
    """
    
    def __init__(self, loki_url: str):
        """
        Initialize the log fetcher.
        
        Args:
            loki_url: URL of the Loki server
        """
        self.loki_url = loki_url.rstrip("/")
        self.parser = LogParser()
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create an HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.loki_timeout_seconds)
            )
        return self._client
    
    async def check_connection(self) -> bool:
        """Check if Loki is reachable."""
        client = await self._get_client()
        
        try:
            response = await client.get(f"{self.loki_url}/ready")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Loki connection check failed: {e}")
            return False
    
    def _build_logql_query(
        self,
        service_name: str,
        namespace: str = "default",
        include_info: bool = False
    ) -> str:
        """
        Build a LogQL query for fetching logs.
        
        Args:
            service_name: Service name to filter
            namespace: Kubernetes namespace
            include_info: Include INFO level logs
            
        Returns:
            LogQL query string
        """
        # Base stream selector
        stream = f'{{service="{service_name}", namespace="{namespace}"}}'
        
        # Add level filter
        if include_info:
            level_filter = '|~ "(?i)(info|warn|warning|error|critical|fatal)"'
        else:
            level_filter = '|~ "(?i)(warn|warning|error|critical|fatal)"'
        
        return f"{stream} {level_filter}"
    
    async def fetch_service_logs(
        self,
        service_name: str,
        namespace: str = "default",
        time_range_minutes: int = 30,
        include_info: bool = False,
        max_logs: int = 100
    ) -> list[LogEntry]:
        """
        Fetch logs for a specific service from Loki.
        
        Args:
            service_name: Name of the service
            namespace: Kubernetes namespace
            time_range_minutes: How far back to fetch logs
            include_info: Include INFO level logs
            max_logs: Maximum number of logs to return
            
        Returns:
            List of parsed LogEntry objects
        """
        client = await self._get_client()
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=time_range_minutes)
        
        # Build query
        query = self._build_logql_query(service_name, namespace, include_info)
        
        try:
            response = await client.get(
                f"{self.loki_url}/loki/api/v1/query_range",
                params={
                    "query": query,
                    "start": int(start_time.timestamp() * 1e9),  # Nanoseconds
                    "end": int(end_time.timestamp() * 1e9),
                    "limit": max_logs,
                    "direction": "backward"  # Most recent first
                }
            )
            
            if response.status_code != 200:
                logger.error(
                    f"Loki query failed: {response.status_code}",
                    extra={"response": response.text}
                )
                return []
            
            data = response.json()
            return self._parse_loki_response(data, service_name, namespace)
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching logs from Loki: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching logs from Loki: {e}")
            return []
    
    def _parse_loki_response(
        self,
        response: dict,
        service_name: str,
        namespace: str
    ) -> list[LogEntry]:
        """
        Parse Loki API response into LogEntry objects.
        
        Args:
            response: Loki API response
            service_name: Service name for context
            namespace: Namespace for context
            
        Returns:
            List of LogEntry objects
        """
        entries = []
        
        # Check response structure
        if response.get("status") != "success":
            logger.warning(f"Loki query status: {response.get('status')}")
            return []
        
        data = response.get("data", {})
        result = data.get("result", [])
        
        for stream in result:
            stream_labels = stream.get("stream", {})
            values = stream.get("values", [])
            
            for timestamp_ns, log_line in values:
                try:
                    # Convert nanoseconds to datetime
                    timestamp = datetime.utcfromtimestamp(int(timestamp_ns) / 1e9)
                    
                    # Parse the log line
                    entry = self.parser.parse(
                        log_line,
                        service=stream_labels.get("service", service_name),
                        namespace=stream_labels.get("namespace", namespace)
                    )
                    entry.timestamp = timestamp
                    
                    entries.append(entry)
                    
                except Exception as e:
                    logger.debug(f"Failed to parse log entry: {e}")
                    continue
        
        logger.info(
            f"Fetched {len(entries)} logs from Loki",
            extra={
                "service": service_name,
                "namespace": namespace,
                "count": len(entries)
            }
        )
        
        return entries
    
    async def fetch_recent_errors(
        self,
        namespace: str = "default",
        time_range_minutes: int = 30,
        max_logs: int = 500
    ) -> list[LogEntry]:
        """
        Fetch all recent error logs across services.
        
        Args:
            namespace: Kubernetes namespace
            time_range_minutes: Time range
            max_logs: Maximum logs
            
        Returns:
            List of error log entries
        """
        client = await self._get_client()
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=time_range_minutes)
        
        # Query all errors in namespace
        query = f'{{namespace="{namespace}"}} |~ "(?i)(error|critical|fatal)"'
        
        try:
            response = await client.get(
                f"{self.loki_url}/loki/api/v1/query_range",
                params={
                    "query": query,
                    "start": int(start_time.timestamp() * 1e9),
                    "end": int(end_time.timestamp() * 1e9),
                    "limit": max_logs,
                    "direction": "backward"
                }
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            return self._parse_loki_response(data, "unknown", namespace)
            
        except Exception as e:
            logger.error(f"Error fetching recent errors: {e}")
            return []
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
