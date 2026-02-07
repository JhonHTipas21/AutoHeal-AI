"""
AutoHeal AI - Metrics Collector
================================

Collects metrics from Prometheus and transforms them into a standardized format.
Supports common infrastructure and application metrics:
- Error rates
- Latency percentiles (P50, P95, P99)
- CPU and memory usage
- Pod restart counts
"""

from datetime import datetime
from typing import Optional
import httpx

# Try to import shared logging
try:
    from shared.utils.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)

from src.api.schemas import ServiceMetrics, MetricValue, MetricType

logger = get_logger(__name__)


class MetricsCollector:
    """
    Collects metrics from Prometheus.
    
    This class handles communication with Prometheus, executing PromQL queries
    and transforming the results into standardized MetricValue objects.
    
    Example:
        collector = MetricsCollector("http://prometheus:9090")
        metrics = await collector.collect_all_metrics()
    """
    
    # PromQL queries for different metric types
    QUERIES = {
        MetricType.ERROR_RATE: """
            sum(rate(http_requests_total{status=~"5.."}[5m])) by (service, namespace)
            /
            sum(rate(http_requests_total[5m])) by (service, namespace)
        """,
        MetricType.LATENCY_P99: """
            histogram_quantile(0.99,
                sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service, namespace)
            ) * 1000
        """,
        MetricType.LATENCY_P95: """
            histogram_quantile(0.95,
                sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service, namespace)
            ) * 1000
        """,
        MetricType.LATENCY_P50: """
            histogram_quantile(0.50,
                sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service, namespace)
            ) * 1000
        """,
        MetricType.CPU_USAGE: """
            sum(rate(container_cpu_usage_seconds_total[5m])) by (pod, namespace)
            /
            sum(container_spec_cpu_quota/container_spec_cpu_period) by (pod, namespace)
            * 100
        """,
        MetricType.MEMORY_USAGE: """
            sum(container_memory_usage_bytes) by (pod, namespace)
            /
            sum(container_spec_memory_limit_bytes) by (pod, namespace)
            * 100
        """,
        MetricType.REQUEST_COUNT: """
            sum(increase(http_requests_total[5m])) by (service, namespace)
        """,
        MetricType.POD_RESTART_COUNT: """
            sum(kube_pod_container_status_restarts_total) by (pod, namespace)
        """,
    }
    
    def __init__(self, prometheus_url: str, timeout_seconds: float = 10.0):
        """
        Initialize the metrics collector.
        
        Args:
            prometheus_url: Base URL of the Prometheus server
            timeout_seconds: HTTP request timeout
        """
        self.prometheus_url = prometheus_url.rstrip("/")
        self.timeout = timeout_seconds
        self._client: httpx.AsyncClient | None = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create an HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout)
            )
        return self._client
    
    async def check_connection(self) -> bool:
        """
        Check if Prometheus is reachable.
        
        Returns:
            True if Prometheus is responding, False otherwise
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{self.prometheus_url}/-/healthy")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Prometheus health check failed: {e}")
            return False
    
    async def query_prometheus(self, query: str) -> list[dict]:
        """
        Execute a PromQL query against Prometheus.
        
        Args:
            query: PromQL query string
            
        Returns:
            List of result dictionaries from Prometheus
        """
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": query.strip()}
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("status") != "success":
                logger.warning(f"Prometheus query failed: {data}")
                return []
            
            return data.get("data", {}).get("result", [])
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error querying Prometheus: {e}")
            return []
        except Exception as e:
            logger.error(f"Error querying Prometheus: {e}")
            return []
    
    def _parse_prometheus_result(
        self,
        results: list[dict],
        metric_type: MetricType
    ) -> list[MetricValue]:
        """
        Parse Prometheus query results into MetricValue objects.
        
        Args:
            results: Raw Prometheus results
            metric_type: Type of metric being parsed
            
        Returns:
            List of parsed MetricValue objects
        """
        metric_values = []
        
        for result in results:
            try:
                # Extract labels
                labels = result.get("metric", {})
                
                # Extract value (instant query returns [timestamp, value])
                value_data = result.get("value", [])
                if len(value_data) >= 2:
                    value = float(value_data[1])
                    
                    # Skip NaN or infinite values
                    if value != value or abs(value) == float("inf"):
                        continue
                    
                    metric_values.append(MetricValue(
                        metric_type=metric_type,
                        value=value,
                        labels=labels,
                        timestamp=datetime.utcnow()
                    ))
            except (ValueError, IndexError, KeyError) as e:
                logger.debug(f"Failed to parse result: {result}, error: {e}")
                continue
        
        return metric_values
    
    async def collect_metric(self, metric_type: MetricType) -> list[MetricValue]:
        """
        Collect a specific metric type from Prometheus.
        
        Args:
            metric_type: Type of metric to collect
            
        Returns:
            List of MetricValue objects
        """
        query = self.QUERIES.get(metric_type)
        if not query:
            logger.warning(f"No query defined for metric type: {metric_type}")
            return []
        
        results = await self.query_prometheus(query)
        return self._parse_prometheus_result(results, metric_type)
    
    async def collect_all_metrics(self) -> list[ServiceMetrics]:
        """
        Collect all metric types and group by service.
        
        Returns:
            List of ServiceMetrics, one per unique service/namespace
        """
        all_metrics: dict[tuple[str, str], list[MetricValue]] = {}
        
        for metric_type in MetricType:
            try:
                metrics = await self.collect_metric(metric_type)
                
                for metric in metrics:
                    # Group by service and namespace
                    service = metric.labels.get("service") or metric.labels.get("pod", "unknown")
                    namespace = metric.labels.get("namespace", "default")
                    key = (service, namespace)
                    
                    if key not in all_metrics:
                        all_metrics[key] = []
                    all_metrics[key].append(metric)
                    
            except Exception as e:
                logger.error(f"Error collecting {metric_type}: {e}")
                continue
        
        # Convert to ServiceMetrics objects
        result = []
        for (service, namespace), metrics in all_metrics.items():
            result.append(ServiceMetrics(
                service_name=service,
                namespace=namespace,
                metrics=metrics,
                collected_at=datetime.utcnow()
            ))
        
        return result
    
    async def collect_service_metrics(
        self,
        service_name: str,
        namespace: str = "default",
        metric_types: Optional[list[str]] = None,
        time_range_minutes: int = 5
    ) -> ServiceMetrics:
        """
        Collect metrics for a specific service.
        
        Args:
            service_name: Name of the service
            namespace: Kubernetes namespace
            metric_types: Optional list of metric types to collect
            time_range_minutes: Time range for queries
            
        Returns:
            ServiceMetrics for the specified service
        """
        metrics = []
        types_to_collect = (
            [MetricType(mt) for mt in metric_types]
            if metric_types
            else list(MetricType)
        )
        
        for metric_type in types_to_collect:
            query = self.QUERIES.get(metric_type, "")
            if not query:
                continue
            
            # Add service filter to query
            # Note: This is a simplified filter - in production, use proper PromQL
            filtered_query = query
            
            results = await self.query_prometheus(filtered_query)
            
            # Filter results by service name
            for result in results:
                labels = result.get("metric", {})
                result_service = labels.get("service") or labels.get("pod", "")
                result_namespace = labels.get("namespace", "default")
                
                if service_name in result_service and namespace == result_namespace:
                    parsed = self._parse_prometheus_result([result], metric_type)
                    metrics.extend(parsed)
        
        return ServiceMetrics(
            service_name=service_name,
            namespace=namespace,
            metrics=metrics,
            collected_at=datetime.utcnow()
        )
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
