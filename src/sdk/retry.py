"""
TRC-8004 SDK 重试机制模块

提供可配置的重试策略，支持指数退避和自定义重试条件。

Classes:
    RetryConfig: 重试配置数据类
    RetryContext: 重试上下文管理器

Functions:
    calculate_delay: 计算重试延迟
    is_retryable: 判断异常是否可重试
    retry: 同步重试装饰器
    retry_async: 异步重试装饰器

Predefined Configs:
    DEFAULT_RETRY_CONFIG: 默认配置（3 次重试，1s 基础延迟）
    AGGRESSIVE_RETRY_CONFIG: 激进配置（5 次重试，0.5s 基础延迟）
    CONSERVATIVE_RETRY_CONFIG: 保守配置（2 次重试，2s 基础延迟）
    NO_RETRY_CONFIG: 不重试

Example:
    >>> from sdk.retry import retry, AGGRESSIVE_RETRY_CONFIG
    >>> @retry(config=AGGRESSIVE_RETRY_CONFIG)
    ... def flaky_operation():
    ...     # 可能失败的操作
    ...     pass

Note:
    - 默认只对网络相关异常进行重试
    - 使用指数退避 + 随机抖动避免惊群效应
    - 可通过 RetryConfig 自定义重试行为
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Callable, Optional, Tuple, Type, TypeVar, Union

from .exceptions import RetryExhaustedError, NetworkError, RPCError, TimeoutError

logger = logging.getLogger("trc8004.retry")

T = TypeVar("T")


@dataclass
class RetryConfig:
    """
    重试配置数据类。

    定义重试行为的所有参数。

    Attributes:
        max_attempts: 最大尝试次数（包括首次尝试）
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        exponential_base: 指数退避基数
        jitter: 是否添加随机抖动
        jitter_factor: 抖动因子（0-1），表示延迟的随机波动范围
        retryable_exceptions: 可重试的异常类型元组
        retry_on_status_codes: 可重试的 HTTP 状态码元组

    Example:
        >>> config = RetryConfig(
        ...     max_attempts=5,
        ...     base_delay=0.5,
        ...     max_delay=30.0,
        ...     jitter=True,
        ... )

    Note:
        - 延迟计算公式: delay = base_delay * (exponential_base ^ (attempt - 1))
        - 抖动范围: delay ± (delay * jitter_factor)
    """

    max_attempts: int = 3
    """最大重试次数（包括首次尝试）"""

    base_delay: float = 1.0
    """基础延迟时间（秒）"""

    max_delay: float = 30.0
    """最大延迟时间（秒）"""

    exponential_base: float = 2.0
    """指数退避基数"""

    jitter: bool = True
    """是否添加随机抖动"""

    jitter_factor: float = 0.1
    """抖动因子（0-1）"""

    retryable_exceptions: Tuple[Type[Exception], ...] = field(
        default_factory=lambda: (
            NetworkError,
            RPCError,
            TimeoutError,
            ConnectionError,
            OSError,
        )
    )
    """可重试的异常类型"""

    retry_on_status_codes: Tuple[int, ...] = (429, 500, 502, 503, 504)
    """可重试的 HTTP 状态码"""


# ============ 预定义配置 ============

DEFAULT_RETRY_CONFIG = RetryConfig()
"""默认重试配置：3 次尝试，1s 基础延迟，指数退避"""

AGGRESSIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=60.0,
    exponential_base=2.0,
)
"""激进重试配置：5 次尝试，0.5s 基础延迟，适用于关键操作"""

CONSERVATIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=2.0,
    max_delay=10.0,
    exponential_base=1.5,
)
"""保守重试配置：2 次尝试，2s 基础延迟，适用于非关键操作"""

NO_RETRY_CONFIG = RetryConfig(max_attempts=1)
"""不重试配置：仅尝试一次"""


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    计算第 N 次重试的延迟时间。

    使用指数退避算法，可选添加随机抖动。

    Args:
        attempt: 当前尝试次数（从 1 开始）
        config: 重试配置

    Returns:
        延迟时间（秒），第一次尝试返回 0

    Example:
        >>> config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)
        >>> calculate_delay(1, config)  # 第一次尝试
        0.0
        >>> calculate_delay(2, config)  # 第一次重试
        1.0
        >>> calculate_delay(3, config)  # 第二次重试
        2.0

    Note:
        - 延迟公式: base_delay * (exponential_base ^ (attempt - 2))
        - 抖动范围: delay ± (delay * jitter_factor)
        - 延迟不会超过 max_delay
    """
    if attempt <= 1:
        return 0.0

    # 指数退避
    delay = config.base_delay * (config.exponential_base ** (attempt - 2))

    # 限制最大延迟
    delay = min(delay, config.max_delay)

    # 添加抖动
    if config.jitter:
        jitter_range = delay * config.jitter_factor
        delay += random.uniform(-jitter_range, jitter_range)

    return max(0.0, delay)


def is_retryable(exception: Exception, config: RetryConfig) -> bool:
    """
    判断异常是否可重试。

    检查异常类型和 HTTP 状态码。

    Args:
        exception: 捕获的异常
        config: 重试配置

    Returns:
        是否应该重试

    Example:
        >>> from sdk.exceptions import NetworkError
        >>> is_retryable(NetworkError("timeout"), DEFAULT_RETRY_CONFIG)
        True
        >>> is_retryable(ValueError("invalid"), DEFAULT_RETRY_CONFIG)
        False

    Note:
        - 检查异常是否是 retryable_exceptions 中的类型
        - 检查 HTTP 响应状态码是否在 retry_on_status_codes 中
    """
    # 检查异常类型
    if isinstance(exception, config.retryable_exceptions):
        return True

    # 检查 HTTP 状态码
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
    同步重试装饰器。

    自动重试被装饰的函数，直到成功或达到最大重试次数。

    Args:
        config: 重试配置，默认使用 DEFAULT_RETRY_CONFIG
        operation_name: 操作名称，用于日志记录

    Returns:
        装饰器函数

    Raises:
        RetryExhaustedError: 重试次数耗尽
        Exception: 不可重试的异常会直接抛出

    Example:
        >>> @retry(config=AGGRESSIVE_RETRY_CONFIG, operation_name="register_agent")
        ... def register_agent():
        ...     # 可能失败的操作
        ...     pass
        >>>
        >>> # 使用默认配置
        >>> @retry()
        ... def another_operation():
        ...     pass

    Note:
        - 只对 config.retryable_exceptions 中的异常进行重试
        - 每次重试前会等待 calculate_delay 计算的时间
        - 日志会记录每次重试的信息
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

            # 不应该到达这里
            raise RetryExhaustedError(op_name, config.max_attempts, last_exception)

        return wrapper

    return decorator


def retry_async(
    config: Optional[RetryConfig] = None,
    operation_name: Optional[str] = None,
) -> Callable:
    """
    异步重试装饰器。

    与 retry 相同，但用于异步函数。

    Args:
        config: 重试配置
        operation_name: 操作名称

    Returns:
        异步装饰器函数

    Example:
        >>> @retry_async(config=DEFAULT_RETRY_CONFIG)
        ... async def async_operation():
        ...     # 异步操作
        ...     pass

    Note:
        使用 asyncio.sleep 进行异步等待。
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
    重试上下文管理器。

    用于手动控制重试逻辑，适用于需要更细粒度控制的场景。

    Attributes:
        config: 重试配置
        operation: 操作名称
        attempt: 当前尝试次数
        last_exception: 最后一次异常

    Args:
        config: 重试配置，默认使用 DEFAULT_RETRY_CONFIG
        operation: 操作名称，用于日志和错误消息

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
        - 必须调用 next_attempt() 开始每次尝试
        - 成功时调用 success()，失败时调用 failed(exception)
        - 重试耗尽时会自动抛出 RetryExhaustedError
    """

    def __init__(
        self,
        config: Optional[RetryConfig] = None,
        operation: str = "operation",
    ) -> None:
        """
        初始化重试上下文。

        Args:
            config: 重试配置
            operation: 操作名称
        """
        self.config = config or DEFAULT_RETRY_CONFIG
        self.operation = operation
        self.attempt = 0
        self.last_exception: Optional[Exception] = None
        self._succeeded = False

    def __enter__(self) -> "RetryContext":
        """进入上下文。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """
        退出上下文。

        如果操作未成功且重试耗尽，抛出 RetryExhaustedError。
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
        检查是否应该继续重试。

        Returns:
            如果未成功且未达到最大尝试次数，返回 True
        """
        if self._succeeded:
            return False
        return self.attempt < self.config.max_attempts

    def next_attempt(self) -> int:
        """
        开始下一次尝试。

        如果不是第一次尝试，会等待计算的延迟时间。

        Returns:
            当前尝试次数
        """
        self.attempt += 1

        if self.attempt > 1:
            delay = calculate_delay(self.attempt, self.config)
            if delay > 0:
                time.sleep(delay)

        return self.attempt

    def failed(self, exception: Exception) -> None:
        """
        标记当前尝试失败。

        如果异常不可重试或重试耗尽，会立即抛出异常。

        Args:
            exception: 当前尝试的异常

        Raises:
            exception: 如果异常不可重试
            RetryExhaustedError: 如果重试耗尽
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
        标记操作成功。

        调用后 should_retry() 将返回 False。
        """
        self._succeeded = True
