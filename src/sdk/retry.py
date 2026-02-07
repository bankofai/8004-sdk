"""
TRON-8004 SDK Retry Mechanism Module

Provides configurable retry strategies, supporting exponential backoff and custom retry conditions.

Classes:
    RetryConfig: Retry configuration data class
    RetryContext: Retry context manager

Functions:
    calculate_delay: Calculate retry delay
    is_retryable: Determine if an exception is retryable
    retry: Synchronous retry decorator
    retry_async: Asynchronous retry decorator

Predefined Configs:
    DEFAULT_RETRY_CONFIG: Default configuration (3 retries, 1s base delay)
    AGGRESSIVE_RETRY_CONFIG: Aggressive configuration (5 retries, 0.5s base delay)
    CONSERVATIVE_RETRY_CONFIG: Conservative configuration (2 retries, 2s base delay)
    NO_RETRY_CONFIG: No retry

Example:
    >>> from sdk.retry import retry, AGGRESSIVE_RETRY_CONFIG
    >>> @retry(config=AGGRESSIVE_RETRY_CONFIG)
    ... def flaky_operation():
    ...     # Potentially failing operation
    ...     pass

Note:
    - Retries only on network-related exceptions by default
    - Uses exponential backoff + random jitter to avoid thundering herd problem
    - Retry behavior can be customized via RetryConfig
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Callable, Optional, Tuple, Type, TypeVar, Union

from .exceptions import RetryExhaustedError, NetworkError, RPCError, TimeoutError

logger = logging.getLogger("tron8004.retry")

T = TypeVar("T")


@dataclass
class RetryConfig:
    """
    Retry configuration data class.

    Defines all parameters for retry behavior.

    Attributes:
        max_attempts: Maximum number of attempts (including the first attempt)
        base_delay: Base delay time (seconds)
        max_delay: Maximum delay time (seconds)
        exponential_base: Exponential backoff base
        jitter: Whether to add random jitter
        jitter_factor: Jitter factor (0-1), indicating the range of random fluctuation of delay
        retryable_exceptions: Tuple of retryable exception types
        retry_on_status_codes: Tuple of retryable HTTP status codes

    Example:
        >>> config = RetryConfig(
        ...     max_attempts=5,
        ...     base_delay=0.5,
        ...     max_delay=30.0,
        ...     jitter=True,
        ... )

    Note:
        - Delay formula: delay = base_delay * (exponential_base ^ (attempt - 1))
        - Jitter range: delay ± (delay * jitter_factor)
    """

    max_attempts: int = 3
    """Maximum retry attempts (including first attempt)"""

    base_delay: float = 1.0
    """Base delay time (seconds)"""

    max_delay: float = 30.0
    """Maximum delay time (seconds)"""

    exponential_base: float = 2.0
    """Exponential backoff base"""

    jitter: bool = True
    """Whether to add random jitter"""

    jitter_factor: float = 0.1
    """Jitter factor (0-1)"""

    retryable_exceptions: Tuple[Type[Exception], ...] = field(
        default_factory=lambda: (
            NetworkError,
            RPCError,
            TimeoutError,
            ConnectionError,
            OSError,
        )
    )
    """Retryable exception types"""

    retry_on_status_codes: Tuple[int, ...] = (429, 500, 502, 503, 504)
    """Retryable HTTP status codes"""


# ============ Predefined Configs ============

DEFAULT_RETRY_CONFIG = RetryConfig()
"""Default retry config: 3 attempts, 1s base delay, exponential backoff"""

AGGRESSIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=60.0,
    exponential_base=2.0,
)
"""Aggressive retry config: 5 attempts, 0.5s base delay, suitable for critical operations"""

CONSERVATIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=2.0,
    max_delay=10.0,
    exponential_base=1.5,
)
"""Conservative retry config: 2 attempts, 2s base delay, suitable for non-critical operations"""

NO_RETRY_CONFIG = RetryConfig(max_attempts=1)
"""No retry config: attempt only once"""


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calculate the delay time for the Nth retry.

    Uses exponential backoff algorithm, optionally adding random jitter.

    Args:
        attempt: Current attempt number (starts from 1)
        config: Retry configuration

    Returns:
        Delay time (seconds), return 0 for the first attempt

    Example:
        >>> config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)
        >>> calculate_delay(1, config)  # First attempt
        0.0
        >>> calculate_delay(2, config)  # First retry
        1.0
        >>> calculate_delay(3, config)  # Second retry
        2.0

    Note:
        - Delay formula: base_delay * (exponential_base ^ (attempt - 2))
        - Jitter range: delay ± (delay * jitter_factor)
        - Delay will not exceed max_delay
    """
    if attempt <= 1:
        return 0.0

    # Exponential backoff
    delay = config.base_delay * (config.exponential_base ** (attempt - 2))

    # Cap at max delay
    delay = min(delay, config.max_delay)

    # Add jitter
    if config.jitter:
        jitter_range = delay * config.jitter_factor
        delay += random.uniform(-jitter_range, jitter_range)

    return max(0.0, delay)


def is_retryable(exception: Exception, config: RetryConfig) -> bool:
    """
    Determine if an exception is retryable.

    Checks exception type and HTTP status code.

    Args:
        exception: Caught exception
        config: Retry configuration

    Returns:
        Whether to retry

    Example:
        >>> from sdk.exceptions import NetworkError
        >>> is_retryable(NetworkError("timeout"), DEFAULT_RETRY_CONFIG)
        True
        >>> is_retryable(ValueError("invalid"), DEFAULT_RETRY_CONFIG)
        False

    Note:
        - Check if exception is in retryable_exceptions types
        - Check if HTTP response status code is in retry_on_status_codes
    """
    # Check exception type
    if isinstance(exception, config.retryable_exceptions):
        return True

    # Check HTTP status code
    if hasattr(exception, "response"):
        response = getattr(exception, "response", None)
        if response is not None and hasattr(response, "status_code"):
            return response.status_code in config.retry_on_status_codes

    return False


def retry(
    config: Optional[RetryConfig] = None,
    operation_name: Optional[str] = None,
) -> Callable:
    """
    Synchronous retry decorator.

    Automatically retries the decorated function until success or max retries reached.

    Args:
        config: Retry configuration, defaults to DEFAULT_RETRY_CONFIG
        operation_name: Operation name, used for logging

    Returns:
        Decorator function

    Raises:
        RetryExhaustedError: Retries exhausted
        Exception: Non-retryable exceptions are raised directly

    Example:
        >>> @retry(config=AGGRESSIVE_RETRY_CONFIG, operation_name="register_agent")
        ... def register_agent():
        ...     # Potentially failing operation
        ...     pass
        >>>
        >>> # Use default config
        >>> @retry()
        ... def another_operation():
        ...     pass

    Note:
        - Only retries exceptions in config.retryable_exceptions
        - Waits for calculate_delay time before each retry
        - Logs info for each retry
    """
    if config is None:
        config = DEFAULT_RETRY_CONFIG

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        op_name = operation_name or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not is_retryable(e, config):
                        logger.debug(
                            "Non-retryable exception in %s: %s",
                            op_name,
                            type(e).__name__,
                        )
                        raise

                    if attempt >= config.max_attempts:
                        logger.warning(
                            "Retry exhausted for %s after %d attempts: %s",
                            op_name,
                            attempt,
                            str(e),
                        )
                        raise RetryExhaustedError(op_name, attempt, e) from e

                    delay = calculate_delay(attempt + 1, config)
                    logger.info(
                        "Retrying %s (attempt %d/%d) after %.2fs: %s",
                        op_name,
                        attempt,
                        config.max_attempts,
                        delay,
                        str(e),
                    )
                    time.sleep(delay)

            # Should not reach here
            raise RetryExhaustedError(op_name, config.max_attempts, last_exception)

        return wrapper

    return decorator


def retry_async(
    config: Optional[RetryConfig] = None,
    operation_name: Optional[str] = None,
) -> Callable:
    """
    Asynchronous retry decorator.

    Same as retry, but for async functions.

    Args:
        config: Retry configuration
        operation_name: Operation name

    Returns:
        Async decorator function

    Example:
        >>> @retry_async(config=DEFAULT_RETRY_CONFIG)
        ... async def async_operation():
        ...     # Async operation
        ...     pass

    Note:
        Uses asyncio.sleep for async waiting.
    """
    if config is None:
        config = DEFAULT_RETRY_CONFIG

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        op_name = operation_name or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception: Optional[Exception] = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not is_retryable(e, config):
                        raise

                    if attempt >= config.max_attempts:
                        raise RetryExhaustedError(op_name, attempt, e) from e

                    delay = calculate_delay(attempt + 1, config)
                    logger.info(
                        "Retrying %s (attempt %d/%d) after %.2fs",
                        op_name,
                        attempt,
                        config.max_attempts,
                        delay,
                    )
                    await asyncio.sleep(delay)

            raise RetryExhaustedError(op_name, config.max_attempts, last_exception)

        return wrapper

    return decorator


class RetryContext:
    """
    Retry context manager.

    Used for manual retry control, suitable for scenarios requiring fine-grained control.

    Attributes:
        config: Retry configuration
        operation: Operation name
        attempt: Current attempt number
        last_exception: Last exception

    Args:
        config: Retry configuration, defaults to DEFAULT_RETRY_CONFIG
        operation: Operation name, used for logging and error messages

    Example:
        >>> with RetryContext(config=DEFAULT_RETRY_CONFIG, operation="send_tx") as ctx:
        ...     while ctx.should_retry():
        ...         ctx.next_attempt()
        ...         try:
        ...             result = do_something()
        ...             ctx.success()
        ...             break
        ...         except Exception as e:
        ...             ctx.failed(e)

    Note:
        - Must call next_attempt() to start each attempt
        - Call success() on success, failed(exception) on failure
        - Automatically raises RetryExhaustedError when retries are exhausted
    """

    def __init__(
        self,
        config: Optional[RetryConfig] = None,
        operation: str = "operation",
    ) -> None:
        """
        Initialize retry context.

        Args:
            config: Retry configuration
            operation: Operation name
        """
        self.config = config or DEFAULT_RETRY_CONFIG
        self.operation = operation
        self.attempt = 0
        self.last_exception: Optional[Exception] = None
        self._succeeded = False

    def __enter__(self) -> "RetryContext":
        """Enter context."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """
        Exit context.

        If operation failed and retries exhausted, raise RetryExhaustedError.
        """
        if exc_type is not None and not self._succeeded:
            if self.attempt >= self.config.max_attempts:
                raise RetryExhaustedError(
                    self.operation,
                    self.attempt,
                    self.last_exception or exc_val,
                )
        return False

    def should_retry(self) -> bool:
        """
        Check if should continue retrying.

        Returns:
            True if not failed and max attempts not reached
        """
        if self._succeeded:
            return False
        return self.attempt < self.config.max_attempts

    def next_attempt(self) -> int:
        """
        Start next attempt.

        If not the first attempt, waits for the calculated delay time.

        Returns:
            Current attempt number
        """
        self.attempt += 1

        if self.attempt > 1:
            delay = calculate_delay(self.attempt, self.config)
            if delay > 0:
                time.sleep(delay)

        return self.attempt

    def failed(self, exception: Exception) -> None:
        """
        Mark current attempt as failed.

        If exception is not retryable or retries exhausted, raises exception immediately.

        Args:
            exception: Exception from current attempt

        Raises:
            exception: If exception is not retryable
            RetryExhaustedError: If retries exhausted
        """
        self.last_exception = exception

        if not is_retryable(exception, self.config):
            raise exception

        if self.attempt >= self.config.max_attempts:
            raise RetryExhaustedError(
                self.operation,
                self.attempt,
                exception,
            ) from exception

        logger.info(
            "Attempt %d/%d failed for %s: %s",
            self.attempt,
            self.config.max_attempts,
            self.operation,
            str(exception),
        )

    def success(self) -> None:
        """
        Mark operation as successful.

        should_retry() will return False after calling this.
        """
        self._succeeded = True
