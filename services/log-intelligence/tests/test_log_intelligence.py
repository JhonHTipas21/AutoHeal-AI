"""
AutoHeal AI - Log Intelligence Service Tests
==============================================

Unit tests for the log intelligence service components.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.api.schemas import (
    LogEntry,
    LogLevel,
    LogBatch,
    ErrorCategory,
    AnalysisRequest,
)


class TestLogSchemas:
    """Tests for Pydantic log schemas."""
    
    def test_log_entry_creation(self):
        """Test creating a LogEntry instance."""
        entry = LogEntry(
            timestamp=datetime.utcnow(),
            service="payment-service",
            namespace="production",
            level=LogLevel.ERROR,
            message="Connection refused to database",
        )
        
        assert entry.service == "payment-service"
        assert entry.level == LogLevel.ERROR
        assert "Connection refused" in entry.message
    
    def test_log_batch_creation(self):
        """Test creating a LogBatch instance."""
        batch = LogBatch(
            logs=[
                LogEntry(
                    timestamp=datetime.utcnow(),
                    service="api-gateway",
                    level=LogLevel.WARNING,
                    message="High latency detected"
                ),
                LogEntry(
                    timestamp=datetime.utcnow(),
                    service="api-gateway",
                    level=LogLevel.ERROR,
                    message="Request timeout"
                )
            ],
            source="test"
        )
        
        assert len(batch.logs) == 2
        assert batch.source == "test"


class TestLogParser:
    """Tests for the LogParser class."""
    
    def test_parse_json_log(self):
        """Test parsing a JSON structured log."""
        from src.core.log_parser import LogParser
        
        parser = LogParser("test-service")
        
        json_log = {
            "timestamp": "2024-01-15T10:30:00Z",
            "level": "error",
            "message": "Failed to connect to database",
            "service": "payment-service",
            "namespace": "production",
            "trace_id": "abc123"
        }
        
        entry = parser.parse_json_log(json_log)
        
        assert entry.service == "payment-service"
        assert entry.level == LogLevel.ERROR
        assert entry.trace_id == "abc123"
    
    def test_parse_text_log(self):
        """Test parsing a plain text log."""
        from src.core.log_parser import LogParser
        
        parser = LogParser("default-service")
        
        text_log = "2024-01-15 10:30:00 ERROR Connection refused"
        
        entry = parser.parse_text_log(text_log, service="api")
        
        assert entry.service == "api"
        assert entry.level == LogLevel.ERROR
    
    def test_parse_level_variations(self):
        """Test parsing various log level formats."""
        from src.core.log_parser import LogParser
        
        parser = LogParser()
        
        assert parser.parse_level("error") == LogLevel.ERROR
        assert parser.parse_level("ERROR") == LogLevel.ERROR
        assert parser.parse_level("warn") == LogLevel.WARNING
        assert parser.parse_level("WARNING") == LogLevel.WARNING
        assert parser.parse_level("info") == LogLevel.INFO
        assert parser.parse_level("CRITICAL") == LogLevel.CRITICAL


class TestSLMAnalyzer:
    """Tests for the SLM analyzer."""
    
    @pytest.fixture
    def mock_analyzer(self):
        """Create a mock SLM analyzer."""
        from src.core.slm_analyzer import MockSLMAnalyzer
        return MockSLMAnalyzer()
    
    @pytest.mark.asyncio
    async def test_classify_null_pointer_error(self, mock_analyzer):
        """Test classification of null pointer errors."""
        await mock_analyzer.initialize()
        
        logs = [
            LogEntry(
                timestamp=datetime.utcnow(),
                service="api",
                level=LogLevel.ERROR,
                message="NullPointerException: Cannot invoke method on null object"
            )
        ]
        
        analyses = await mock_analyzer.analyze_logs(logs)
        
        assert len(analyses) == 1
        assert analyses[0].category == ErrorCategory.NULL_POINTER
        assert analyses[0].confidence > 0.8
    
    @pytest.mark.asyncio
    async def test_classify_connection_error(self, mock_analyzer):
        """Test classification of connection errors."""
        await mock_analyzer.initialize()
        
        logs = [
            LogEntry(
                timestamp=datetime.utcnow(),
                service="api",
                level=LogLevel.ERROR,
                message="Connection refused to host:5432"
            )
        ]
        
        analyses = await mock_analyzer.analyze_logs(logs)
        
        assert len(analyses) == 1
        assert analyses[0].category == ErrorCategory.CONNECTION_ERROR
    
    @pytest.mark.asyncio
    async def test_classify_timeout_error(self, mock_analyzer):
        """Test classification of timeout errors."""
        await mock_analyzer.initialize()
        
        logs = [
            LogEntry(
                timestamp=datetime.utcnow(),
                service="api",
                level=LogLevel.ERROR,
                message="Request timed out after 30s"
            )
        ]
        
        analyses = await mock_analyzer.analyze_logs(logs)
        
        assert len(analyses) == 1
        assert analyses[0].category == ErrorCategory.TIMEOUT
    
    @pytest.mark.asyncio
    async def test_group_similar_logs(self, mock_analyzer):
        """Test that similar logs are grouped together."""
        await mock_analyzer.initialize()
        
        # Create 5 similar logs
        logs = [
            LogEntry(
                timestamp=datetime.utcnow(),
                service="api",
                level=LogLevel.ERROR,
                message=f"Connection refused to host:5432 (attempt {i})"
            )
            for i in range(5)
        ]
        
        analyses = await mock_analyzer.analyze_logs(logs)
        
        # Should be grouped into one pattern
        assert len(analyses) == 1
        assert analyses[0].occurrence_count == 5


class TestLogFetcher:
    """Tests for the LogFetcher class."""
    
    @pytest.fixture
    def fetcher(self):
        """Create a LogFetcher for testing."""
        from src.core.log_fetcher import LogFetcher
        return LogFetcher("http://loki:3100")
    
    @pytest.mark.asyncio
    async def test_build_logql_query(self, fetcher):
        """Test LogQL query building."""
        query = fetcher._build_logql_query("payment-service", "production")
        
        assert "payment-service" in query
        assert "production" in query
        assert "error" in query.lower() or "warn" in query.lower()
    
    @pytest.mark.asyncio
    async def test_check_connection_failure(self, fetcher):
        """Test connection check handles failure gracefully."""
        with patch.object(fetcher, '_get_client') as mock_get:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Connection refused")
            mock_get.return_value = mock_client
            
            result = await fetcher.check_connection()
            
            assert result is False


class TestCommitCorrelator:
    """Tests for the CommitCorrelator class."""
    
    @pytest.fixture
    def correlator(self):
        """Create a CommitCorrelator for testing."""
        from src.core.commit_correlator import CommitCorrelator
        return CommitCorrelator()  # No repo URL = mock mode
    
    @pytest.mark.asyncio
    async def test_mock_correlation(self, correlator):
        """Test that mock correlation returns expected structure."""
        result = await correlator.correlate(
            error_pattern="Connection refused",
            service_name="payment-service"
        )
        
        assert result.error_pattern == "Connection refused"
        assert len(result.correlated_commits) > 0
        assert 0 <= result.correlation_confidence <= 1
    
    def test_extract_keywords(self, correlator):
        """Test keyword extraction from error patterns."""
        keywords = correlator._extract_keywords(
            "NullPointerException at PaymentService.processOrder"
        )
        
        assert "nullpointerexception" in keywords
        assert "paymentservice" in keywords
        assert "processorder" in keywords


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
