"""
AutoHeal AI - Monitoring Service Tests
=======================================

Unit tests for the monitoring service components.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.api.schemas import (
    MetricType,
    MetricValue,
    ServiceMetrics,
    ThresholdConfig,
)


class TestMetricSchemas:
    """Tests for Pydantic metric schemas."""
    
    def test_metric_value_creation(self):
        """Test creating a MetricValue instance."""
        metric = MetricValue(
            metric_type=MetricType.ERROR_RATE,
            value=0.05,
            labels={"service": "test-svc", "namespace": "default"}
        )
        
        assert metric.metric_type == MetricType.ERROR_RATE
        assert metric.value == 0.05
        assert metric.labels["service"] == "test-svc"
        assert metric.timestamp is not None
    
    def test_service_metrics_creation(self):
        """Test creating a ServiceMetrics instance."""
        metrics = ServiceMetrics(
            service_name="payment-service",
            namespace="production",
            metrics=[
                MetricValue(
                    metric_type=MetricType.ERROR_RATE,
                    value=0.02,
                    labels={}
                ),
                MetricValue(
                    metric_type=MetricType.LATENCY_P99,
                    value=250.5,
                    labels={}
                )
            ]
        )
        
        assert metrics.service_name == "payment-service"
        assert metrics.namespace == "production"
        assert len(metrics.metrics) == 2
    
    def test_threshold_config_defaults(self):
        """Test ThresholdConfig default values."""
        config = ThresholdConfig()
        
        assert config.error_rate == 0.05
        assert config.latency_p99_ms == 1000
        assert config.latency_p95_ms == 500
        assert config.cpu_percent == 80
        assert config.memory_percent == 85


class TestAnomalyDetector:
    """Tests for the AnomalyDetector class."""
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        settings = MagicMock()
        settings.anomaly_threshold_error_rate = 0.05
        settings.anomaly_threshold_latency_p99_ms = 1000
        settings.anomaly_threshold_latency_p95_ms = 500
        settings.anomaly_threshold_cpu_percent = 80
        settings.anomaly_threshold_memory_percent = 85
        settings.alert_cooldown_seconds = 60
        return settings
    
    def test_detect_error_rate_anomaly(self, mock_settings):
        """Test detection of error rate anomaly."""
        from src.core.anomaly_detector import AnomalyDetector
        
        detector = AnomalyDetector(mock_settings)
        
        # Create metrics with high error rate
        service_metrics = [
            ServiceMetrics(
                service_name="test-service",
                namespace="default",
                metrics=[
                    MetricValue(
                        metric_type=MetricType.ERROR_RATE,
                        value=0.15,  # 15% error rate, above 5% threshold
                        labels={}
                    )
                ]
            )
        ]
        
        anomalies = detector.detect_anomalies(service_metrics)
        
        assert len(anomalies) == 1
        assert anomalies[0].target_service == "test-service"
        assert anomalies[0].current_value == 0.15
    
    def test_no_anomaly_below_threshold(self, mock_settings):
        """Test that no anomaly is detected when below threshold."""
        from src.core.anomaly_detector import AnomalyDetector
        
        detector = AnomalyDetector(mock_settings)
        
        service_metrics = [
            ServiceMetrics(
                service_name="healthy-service",
                namespace="default",
                metrics=[
                    MetricValue(
                        metric_type=MetricType.ERROR_RATE,
                        value=0.01,  # 1% error rate, below threshold
                        labels={}
                    ),
                    MetricValue(
                        metric_type=MetricType.LATENCY_P99,
                        value=500,  # 500ms, below 1000ms threshold
                        labels={}
                    )
                ]
            )
        ]
        
        anomalies = detector.detect_anomalies(service_metrics)
        
        assert len(anomalies) == 0
    
    def test_cooldown_prevents_duplicate_alerts(self, mock_settings):
        """Test that cooldown prevents duplicate anomalies."""
        from src.core.anomaly_detector import AnomalyDetector
        
        mock_settings.alert_cooldown_seconds = 300  # 5 minutes
        detector = AnomalyDetector(mock_settings)
        
        service_metrics = [
            ServiceMetrics(
                service_name="test-service",
                namespace="default",
                metrics=[
                    MetricValue(
                        metric_type=MetricType.ERROR_RATE,
                        value=0.10,
                        labels={}
                    )
                ]
            )
        ]
        
        # First detection should succeed
        anomalies1 = detector.detect_anomalies(service_metrics)
        assert len(anomalies1) == 1
        
        # Second detection should be blocked by cooldown
        anomalies2 = detector.detect_anomalies(service_metrics)
        assert len(anomalies2) == 0


class TestMetricsCollector:
    """Tests for the MetricsCollector class."""
    
    @pytest.fixture
    def collector(self):
        """Create a MetricsCollector for testing."""
        from src.core.metrics_collector import MetricsCollector
        return MetricsCollector("http://prometheus:9090")
    
    @pytest.mark.asyncio
    async def test_check_connection_success(self, collector):
        """Test successful Prometheus connection check."""
        with patch.object(collector, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            result = await collector.check_connection()
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_check_connection_failure(self, collector):
        """Test failed Prometheus connection check."""
        with patch.object(collector, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Connection refused")
            mock_get_client.return_value = mock_client
            
            result = await collector.check_connection()
            
            assert result is False


class TestAlerter:
    """Tests for the Alerter class."""
    
    @pytest.fixture
    def alerter(self):
        """Create an Alerter for testing."""
        from src.core.alerter import Alerter
        return Alerter("http://incident-manager:8002")
    
    @pytest.mark.asyncio
    async def test_send_anomaly_event_success(self, alerter):
        """Test successful anomaly event sending."""
        # Create a mock event
        mock_event = MagicMock()
        mock_event.event_id = "test-123"
        mock_event.anomaly_type.value = "error_rate_spike"
        mock_event.target_service = "test-svc"
        mock_event.model_dump.return_value = {"event_id": "test-123"}
        
        with patch.object(alerter, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            result = await alerter.send_anomaly_event(mock_event)
            
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
