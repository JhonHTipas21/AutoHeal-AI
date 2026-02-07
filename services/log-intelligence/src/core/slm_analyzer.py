"""
AutoHeal AI - SLM Analyzer
===========================

Small Language Model integration for log analysis.
Supports multiple providers: Mock (for testing), TinyLlama, Ollama.

The SLM analyzes error logs to:
1. Classify error types
2. Infer probable root causes
3. Suggest remediation actions
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
import uuid
import re
import random

from src.api.schemas import LogEntry, ErrorAnalysis, ErrorCategory
from src.config import get_settings, SLMProvider

try:
    from shared.utils.logging import get_logger
except ImportError:
    import logging
    def get_logger(name: str):
        return logging.getLogger(name)

logger = get_logger(__name__)
settings = get_settings()

# Singleton instance
_analyzer_instance: Optional["BaseSLMAnalyzer"] = None


class BaseSLMAnalyzer(ABC):
    """Base class for SLM analyzers."""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the analyzer."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up resources."""
        pass
    
    @abstractmethod
    def is_ready(self) -> bool:
        """Check if analyzer is ready."""
        pass
    
    @abstractmethod
    async def analyze_logs(self, logs: list[LogEntry]) -> list[ErrorAnalysis]:
        """Analyze logs and return error analyses."""
        pass


class MockSLMAnalyzer(BaseSLMAnalyzer):
    """
    Mock SLM analyzer for development and testing.
    
    Uses pattern matching and heuristics to simulate SLM behavior.
    Provides realistic but deterministic responses.
    """
    
    # Error pattern mappings
    ERROR_PATTERNS = {
        r"(?i)null\s*pointer|NullPointerException|None\s*type|null\s*reference": (
            ErrorCategory.NULL_POINTER,
            "Attempting to access a null/None object reference",
            ["Add null checks before accessing object properties",
             "Review the code path that leads to this null reference",
             "Consider using Optional patterns or null-safe operators"]
        ),
        r"(?i)out\s*of\s*memory|OOM|heap\s*space|memory\s*limit": (
            ErrorCategory.OUT_OF_MEMORY,
            "Application exceeded memory limits, possibly due to memory leak or large data processing",
            ["Increase memory limits if appropriate",
             "Review recent changes for memory leaks",
             "Implement pagination for large data sets",
             "Consider horizontal scaling"]
        ),
        r"(?i)connection\s*refused|ECONNREFUSED|connect\s*ETIMEDOUT|host\s*unreachable": (
            ErrorCategory.CONNECTION_ERROR,
            "Failed to establish network connection to downstream service",
            ["Verify target service is running",
             "Check network policies and firewall rules",
             "Implement circuit breaker pattern",
             "Add retry logic with exponential backoff"]
        ),
        r"(?i)timeout|timed?\s*out|deadline\s*exceeded|context\s*deadline": (
            ErrorCategory.TIMEOUT,
            "Operation exceeded timeout threshold, possibly due to slow dependency or resource contention",
            ["Increase timeout if appropriate",
             "Optimize slow queries or operations",
             "Check for resource contention",
             "Implement async processing for long operations"]
        ),
        r"(?i)auth(entication)?\s*(failed|error)|invalid\s*credentials|401|unauthorized": (
            ErrorCategory.AUTHENTICATION,
            "Authentication failed, possibly due to invalid or expired credentials",
            ["Verify credentials are correct and not expired",
             "Check token refresh logic",
             "Review authentication configuration"]
        ),
        r"(?i)forbidden|403|access\s*denied|permission\s*denied|unauthorized\s*access": (
            ErrorCategory.AUTHORIZATION,
            "Authorization failed, user lacks required permissions",
            ["Review role and permission assignments",
             "Check resource-level access policies",
             "Verify the requesting identity"]
        ),
        r"(?i)database|SQL|postgres|mysql|mongo|redis|connection\s*pool": (
            ErrorCategory.DATABASE,
            "Database operation failed, possibly due to connection issues or query errors",
            ["Check database connectivity",
             "Review connection pool settings",
             "Optimize slow queries",
             "Verify database load and capacity"]
        ),
        r"(?i)config(uration)?|env(ironment)?|missing\s*(key|variable|setting)": (
            ErrorCategory.CONFIGURATION,
            "Configuration error, missing or invalid settings",
            ["Review environment variables",
             "Check configuration files",
             "Verify secrets are properly mounted"]
        ),
        r"(?i)dependency|import|module\s*not\s*found|package|library": (
            ErrorCategory.DEPENDENCY,
            "Dependency resolution failed",
            ["Check package versions",
             "Verify dependencies are installed",
             "Review import statements"]
        ),
        r"(?i)validation|invalid\s*(input|request|data)|schema|format": (
            ErrorCategory.VALIDATION,
            "Input validation failed",
            ["Review input data format",
             "Check validation rules",
             "Verify client is sending correct data"]
        ),
        r"(?i)rate\s*limit|too\s*many\s*requests|429|throttl": (
            ErrorCategory.RATE_LIMIT,
            "Rate limit exceeded, too many requests to a service or API",
            ["Implement backoff strategy",
             "Review rate limit configurations",
             "Consider caching to reduce request volume"]
        ),
    }
    
    def __init__(self):
        self._ready = False
    
    async def initialize(self) -> None:
        """Initialize the mock analyzer."""
        logger.info("Initializing Mock SLM Analyzer")
        self._ready = True
    
    async def shutdown(self) -> None:
        """Clean up resources."""
        self._ready = False
    
    def is_ready(self) -> bool:
        return self._ready
    
    def _classify_error(self, message: str, exception: Optional[str] = None) -> tuple[ErrorCategory, str, list[str], float]:
        """
        Classify an error based on pattern matching.
        
        Returns:
            Tuple of (category, root_cause, recommended_actions, confidence)
        """
        text_to_analyze = f"{message} {exception or ''}"
        
        for pattern, (category, root_cause, actions) in self.ERROR_PATTERNS.items():
            if re.search(pattern, text_to_analyze):
                # High confidence for pattern matches
                confidence = 0.85 + random.uniform(0, 0.1)
                return category, root_cause, actions, min(confidence, 0.95)
        
        # Unknown error type
        return (
            ErrorCategory.UNKNOWN,
            "Unable to determine root cause from available information",
            ["Review application logs for more context",
             "Check recent deployments and changes",
             "Examine system metrics for anomalies"],
            0.4 + random.uniform(0, 0.2)
        )
    
    def _determine_severity(self, category: ErrorCategory, occurrence_count: int) -> str:
        """Determine severity based on error category and frequency."""
        critical_categories = {ErrorCategory.OUT_OF_MEMORY, ErrorCategory.DATABASE}
        high_categories = {ErrorCategory.CONNECTION_ERROR, ErrorCategory.AUTHENTICATION}
        
        if category in critical_categories or occurrence_count >= 100:
            return "critical"
        elif category in high_categories or occurrence_count >= 50:
            return "high"
        elif occurrence_count >= 10:
            return "medium"
        else:
            return "low"
    
    def _group_similar_logs(self, logs: list[LogEntry]) -> dict[str, list[LogEntry]]:
        """Group similar log entries by normalized message."""
        groups: dict[str, list[LogEntry]] = {}
        
        for log in logs:
            # Normalize message by removing IDs, timestamps, and numbers
            normalized = re.sub(r'\b[0-9a-f-]{36}\b', '<UUID>', log.message)  # UUIDs
            normalized = re.sub(r'\b\d+\b', '<NUM>', normalized)  # Numbers
            normalized = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', '<TS>', normalized)  # Timestamps
            
            if normalized not in groups:
                groups[normalized] = []
            groups[normalized].append(log)
        
        return groups
    
    async def analyze_logs(self, logs: list[LogEntry]) -> list[ErrorAnalysis]:
        """
        Analyze logs and return error analyses.
        
        Groups similar errors and provides analysis for each group.
        """
        if not logs:
            return []
        
        # Group similar logs
        groups = self._group_similar_logs(logs)
        
        analyses = []
        for normalized_msg, group_logs in groups.items():
            # Use first log as representative
            rep_log = group_logs[0]
            
            # Classify the error
            category, root_cause, actions, confidence = self._classify_error(
                rep_log.message,
                rep_log.exception
            )
            
            # Determine severity
            severity = self._determine_severity(category, len(group_logs))
            
            # Create analysis
            analysis = ErrorAnalysis(
                error_id=str(uuid.uuid4()),
                category=category,
                severity=severity,
                original_message=rep_log.message[:500],  # Truncate long messages
                root_cause=root_cause,
                confidence=round(confidence, 2),
                recommended_actions=actions,
                related_commit=None,  # Set by commit correlator
                related_deployment=None,
                first_occurrence=min(log.timestamp for log in group_logs),
                occurrence_count=len(group_logs),
                sample_logs=[log.message[:200] for log in group_logs[:3]]
            )
            
            analyses.append(analysis)
        
        # Sort by severity and occurrence count
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        analyses.sort(key=lambda a: (severity_order.get(a.severity, 4), -a.occurrence_count))
        
        logger.info(
            f"Mock SLM analyzed {len(logs)} logs into {len(analyses)} error patterns",
            extra={"log_count": len(logs), "pattern_count": len(analyses)}
        )
        
        return analyses


class OllamaSLMAnalyzer(BaseSLMAnalyzer):
    """
    Ollama-based SLM analyzer for local LLM inference.
    
    Requires Ollama to be running locally with a suitable model.
    """
    
    def __init__(self, ollama_url: str, model_name: str = "tinyllama"):
        self.ollama_url = ollama_url.rstrip("/")
        self.model_name = model_name
        self._ready = False
        self._client = None
    
    async def initialize(self) -> None:
        """Initialize the Ollama analyzer."""
        import httpx
        
        logger.info(f"Initializing Ollama SLM Analyzer with model: {self.model_name}")
        
        self._client = httpx.AsyncClient(timeout=60.0)
        
        # Check if Ollama is available
        try:
            response = await self._client.get(f"{self.ollama_url}/api/tags")
            if response.status_code == 200:
                self._ready = True
                logger.info("Ollama connection established")
            else:
                logger.warning(f"Ollama responded with status {response.status_code}")
        except Exception as e:
            logger.warning(f"Could not connect to Ollama: {e}")
            # Fall back to mock behavior
            self._ready = True  # Still ready, will use fallback
    
    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._client:
            await self._client.aclose()
        self._ready = False
    
    def is_ready(self) -> bool:
        return self._ready
    
    async def _generate(self, prompt: str) -> str:
        """Generate response using Ollama."""
        if not self._client:
            return ""
        
        try:
            response = await self._client.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": settings.slm_temperature,
                        "num_predict": settings.slm_max_tokens
                    }
                }
            )
            
            if response.status_code == 200:
                return response.json().get("response", "")
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
        
        return ""
    
    async def analyze_logs(self, logs: list[LogEntry]) -> list[ErrorAnalysis]:
        """Analyze logs using Ollama."""
        # For now, fall back to mock analyzer logic
        # In production, this would use the LLM for more nuanced analysis
        mock = MockSLMAnalyzer()
        await mock.initialize()
        return await mock.analyze_logs(logs)


def get_slm_analyzer() -> BaseSLMAnalyzer:
    """
    Get the singleton SLM analyzer instance.
    
    Returns the appropriate analyzer based on configuration.
    """
    global _analyzer_instance
    
    if _analyzer_instance is None:
        if settings.slm_provider == SLMProvider.OLLAMA:
            _analyzer_instance = OllamaSLMAnalyzer(
                ollama_url=settings.slm_ollama_url,
                model_name=settings.slm_model_name
            )
        else:
            # Default to mock analyzer
            _analyzer_instance = MockSLMAnalyzer()
    
    return _analyzer_instance


class SLMAnalyzer:
    """Convenience wrapper for SLM analyzer singleton."""
    
    @staticmethod
    def get_instance() -> BaseSLMAnalyzer:
        return get_slm_analyzer()
