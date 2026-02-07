"""
AutoHeal AI - Retry Utilities
=============================

Provides configurable retry logic with exponential backoff for resilient operations.
Useful for network calls, database operations, and other potentially flaky operations.

Usage:
    from shared.utils.retry import with_retry, RetryConfig
    
    @with_retry(RetryConfig(max_attempts=3, base_delay=1.0))
    async def call_external_service():
        return await http_client.get("/api/data")
"""

import asyncio
from dataclasses import dataclass, field
from functools import wraps
from typing import Callable, Type, TypeVar, Any, Optional
from collections.abc import Awaitable

from shared.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """
    Configuration for retry behavior.
    
    Attributes:
        max_attempts: Maximum number of attempts (including first try)
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay cap in seconds
        backoff_multiplier: Multiplier for exponential backoff
        retryable_exceptions: Tuple of exception types that trigger a retry
        on_retry: Optional callback called before each retry
    """
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    retryable_exceptions: tuple[Type[Exception], ...] = field(
        default_factory=lambda: (Exception,)
    )
    on_retry: Optional[Callable[[int, Exception], None]] = None


def calculate_delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    backoff_multiplier: float
) -> float:
    """
    Calculate the delay for a given retry attempt using exponential backoff.
    
    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay cap
        backoff_multiplier: Multiplier for each successive attempt
        
    Returns:
        Delay in seconds for this attempt
    """
    delay = base_delay * (backoff_multiplier ** attempt)
    return min(delay, max_delay)


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator that adds retry logic to async functions.
    
    The decorated function will be retried on failure according to the
    provided configuration. Uses exponential backoff between retries.
    
    Args:
        config: Retry configuration, uses defaults if not provided
        
    Returns:
        Decorator function
        
    Example:
        @with_retry(RetryConfig(max_attempts=5, base_delay=0.5))
        async def flaky_operation():
            response = await external_api.call()
            return response
            
        # The above will retry up to 5 times with delays of 0.5s, 1s, 2s, 4s
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Optional[Exception] = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    # Check if we have more attempts
                    if attempt + 1 >= config.max_attempts:
                        logger.error(
                            f"All {config.max_attempts} retry attempts exhausted for {func.__name__}",
                            extra={
                                "function": func.__name__,
                                "error": str(e),
                                "attempts": config.max_attempts
                            }
                        )
                        raise
                    
                    # Calculate delay for next retry
                    delay = calculate_delay(
                        attempt,
                        config.base_delay,
                        config.max_delay,
                        config.backoff_multiplier
                    )
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{config.max_attempts} for {func.__name__} after {delay:.2f}s",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "max_attempts": config.max_attempts,
                            "delay": delay,
                            "error": str(e)
                        }
                    )
                    
                    # Call optional retry callback
                    if config.on_retry:
                        config.on_retry(attempt + 1, e)
                    
                    # Wait before retrying
                    await asyncio.sleep(delay)
            
            # This should never be reached, but satisfy type checker
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry loop exited unexpectedly")
        
        return wrapper
    return decorator


async def retry_async(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    config: Optional[RetryConfig] = None,
    **kwargs: Any
) -> T:
    """
    Retry an async function with the given configuration.
    
    Alternative to the decorator for one-off retry operations.
    
    Args:
        func: Async function to retry
        *args: Positional arguments to pass to the function
        config: Retry configuration
        **kwargs: Keyword arguments to pass to the function
        
    Returns:
        Result of the function call
        
    Example:
        result = await retry_async(
            fetch_data,
            user_id=123,
            config=RetryConfig(max_attempts=3)
        )
    """
    if config is None:
        config = RetryConfig()
    
    @with_retry(config)
    async def wrapper() -> T:
        return await func(*args, **kwargs)
    
    return await wrapper()


class CircuitBreaker:
    """
    Simple circuit breaker implementation for preventing cascade failures.
    
    The circuit breaker tracks failures and opens (blocks requests) when
    the failure threshold is reached. After a reset timeout, it allows
    a single request through to test if the service has recovered.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests are blocked
    - HALF_OPEN: Testing if service recovered
    
    Example:
        breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)
        
        async def protected_call():
            if not breaker.can_execute():
                raise CircuitOpenError("Circuit is open")
            try:
                result = await external_service.call()
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
    """
    
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
    
    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        half_open_max_calls: int = 1
    ):
        """
        Initialize the circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            reset_timeout: Seconds to wait before testing recovery
            half_open_max_calls: Max calls allowed in half-open state
        """
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
    
    @property
    def state(self) -> str:
        """Get current circuit state."""
        return self._state
    
    def can_execute(self) -> bool:
        """Check if a request can be executed."""
        if self._state == self.CLOSED:
            return True
        
        if self._state == self.OPEN:
            # Check if reset timeout has passed
            if self._last_failure_time is not None:
                import time
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.reset_timeout:
                    self._state = self.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info("Circuit breaker entering half-open state")
                    return True
            return False
        
        if self._state == self.HALF_OPEN:
            return self._half_open_calls < self.half_open_max_calls
        
        return False
    
    def record_success(self) -> None:
        """Record a successful execution."""
        if self._state == self.HALF_OPEN:
            # Service recovered, close the circuit
            self._state = self.CLOSED
            self._failure_count = 0
            logger.info("Circuit breaker closed - service recovered")
        elif self._state == self.CLOSED:
            # Reset failure count on success
            self._failure_count = 0
    
    def record_failure(self) -> None:
        """Record a failed execution."""
        import time
        
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._state == self.HALF_OPEN:
            # Failed during recovery test, reopen
            self._state = self.OPEN
            logger.warning("Circuit breaker reopened - recovery failed")
        
        elif self._state == self.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._state = self.OPEN
                logger.warning(
                    f"Circuit breaker opened after {self._failure_count} failures"
                )
    
    def reset(self) -> None:
        """Manually reset the circuit breaker to closed state."""
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._half_open_calls = 0
        logger.info("Circuit breaker manually reset")


class CircuitOpenError(Exception):
    """Raised when attempting to execute while circuit is open."""
    pass
