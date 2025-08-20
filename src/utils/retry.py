"""
Retry utilities with exponential backoff for robust error handling.
"""

import asyncio
import time
from functools import wraps
from typing import Optional, Callable, Any, TypeVar, Union
from loguru import logger

T = TypeVar("T")


def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """
    Decorator for automatic retry with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry
        on_retry: Optional callback function called on each retry
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            last_exception = None

            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    last_exception = e

                    if attempt >= max_attempts:
                        logger.error(f"Failed after {max_attempts} attempts in {func.__name__}: {e}")
                        raise

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed in {func.__name__}, "
                        f"retrying in {current_delay:.1f}s: {e}"
                    )

                    if on_retry:
                        on_retry(attempt, e)

                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            last_exception = None

            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    last_exception = e

                    if attempt >= max_attempts:
                        logger.error(f"Failed after {max_attempts} attempts in {func.__name__}: {e}")
                        raise

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed in {func.__name__}, "
                        f"retrying in {current_delay:.1f}s: {e}"
                    )

                    if on_retry:
                        on_retry(attempt, e)

                    time.sleep(current_delay)
                    current_delay *= backoff

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class RetryPolicy:
    """Configurable retry policy for different scenarios."""

    # Quick retry for transient network issues
    QUICK = {"max_attempts": 3, "delay": 0.5, "backoff": 1.5}

    # Standard retry for API calls
    STANDARD = {"max_attempts": 3, "delay": 1.0, "backoff": 2.0}

    # Aggressive retry for critical operations
    AGGRESSIVE = {"max_attempts": 5, "delay": 1.0, "backoff": 2.0}

    # Slow retry for rate-limited APIs
    RATE_LIMITED = {"max_attempts": 3, "delay": 5.0, "backoff": 2.0}

    # Database operations
    DATABASE = {"max_attempts": 3, "delay": 0.5, "backoff": 2.0, "exceptions": (ConnectionError, TimeoutError)}


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    """

    def __init__(
        self, failure_threshold: int = 5, recovery_timeout: float = 60.0, expected_exception: type = Exception
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Time in seconds before attempting to close circuit
            expected_exception: Exception type to track
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function through circuit breaker.
        """
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise Exception(f"Circuit breaker is open for {func.__name__}")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise

    async def async_call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call async function through circuit breaker.
        """
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise Exception(f"Circuit breaker is open for {func.__name__}")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit."""
        return self.last_failure_time and time.time() - self.last_failure_time >= self.recovery_timeout

    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = "closed"

    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")


# Example usage functions
@with_retry(**RetryPolicy.STANDARD)
async def fetch_with_retry(url: str) -> dict:
    """Example function with retry logic."""
    # This would be your actual fetch logic
    pass


@with_retry(max_attempts=5, delay=2.0, backoff=2.0, exceptions=(ConnectionError, TimeoutError))
async def database_operation():
    """Example database operation with custom retry settings."""
    # This would be your actual database operation
    pass
