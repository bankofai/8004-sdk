"""测试重试机制"""

import time
import pytest
from sdk.retry import (
    RetryConfig,
    DEFAULT_RETRY_CONFIG,
    AGGRESSIVE_RETRY_CONFIG,
    CONSERVATIVE_RETRY_CONFIG,
    NO_RETRY_CONFIG,
    calculate_delay,
    is_retryable,
    retry,
    RetryContext,
)
from sdk.exceptions import (
    NetworkError,
    RPCError,
    RetryExhaustedError,
    ContractCallError,
)


class TestRetryConfig:
    """测试重试配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = DEFAULT_RETRY_CONFIG
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.jitter is True

    def test_aggressive_config(self):
        """测试激进配置"""
        config = AGGRESSIVE_RETRY_CONFIG
        assert config.max_attempts == 5
        assert config.base_delay == 0.5

    def test_conservative_config(self):
        """测试保守配置"""
        config = CONSERVATIVE_RETRY_CONFIG
        assert config.max_attempts == 2
        assert config.base_delay == 2.0

    def test_no_retry_config(self):
        """测试不重试配置"""
        config = NO_RETRY_CONFIG
        assert config.max_attempts == 1


class TestCalculateDelay:
    """测试延迟计算"""

    def test_first_attempt_no_delay(self):
        """第一次尝试无延迟"""
        config = RetryConfig(base_delay=1.0, jitter=False)
        assert calculate_delay(1, config) == 0.0

    def test_exponential_backoff(self):
        """测试指数退避"""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)
        assert calculate_delay(2, config) == 1.0  # 1 * 2^0
        assert calculate_delay(3, config) == 2.0  # 1 * 2^1
        assert calculate_delay(4, config) == 4.0  # 1 * 2^2

    def test_max_delay_cap(self):
        """测试最大延迟限制"""
        config = RetryConfig(base_delay=1.0, max_delay=5.0, exponential_base=2.0, jitter=False)
        assert calculate_delay(10, config) == 5.0  # 被限制在 max_delay

    def test_jitter_adds_randomness(self):
        """测试抖动添加随机性"""
        config = RetryConfig(base_delay=1.0, jitter=True, jitter_factor=0.5)
        delays = [calculate_delay(2, config) for _ in range(10)]
        # 应该有不同的值
        assert len(set(delays)) > 1


class TestIsRetryable:
    """测试可重试判断"""

    def test_network_error_retryable(self):
        """网络错误可重试"""
        config = DEFAULT_RETRY_CONFIG
        assert is_retryable(NetworkError("timeout"), config) is True
        assert is_retryable(RPCError("failed"), config) is True

    def test_contract_error_not_retryable(self):
        """合约错误不可重试"""
        config = DEFAULT_RETRY_CONFIG
        assert is_retryable(ContractCallError("c", "m", "revert"), config) is False

    def test_connection_error_retryable(self):
        """连接错误可重试"""
        config = DEFAULT_RETRY_CONFIG
        assert is_retryable(ConnectionError("refused"), config) is True


class TestRetryDecorator:
    """测试重试装饰器"""

    def test_success_no_retry(self):
        """成功时不重试"""
        call_count = 0

        @retry(config=DEFAULT_RETRY_CONFIG)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = success_func()
        assert result == "ok"
        assert call_count == 1

    def test_retry_on_network_error(self):
        """网络错误时重试"""
        call_count = 0

        @retry(config=RetryConfig(max_attempts=3, base_delay=0.01, jitter=False))
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("timeout")
            return "ok"

        result = flaky_func()
        assert result == "ok"
        assert call_count == 3

    def test_no_retry_on_contract_error(self):
        """合约错误不重试"""
        call_count = 0

        @retry(config=DEFAULT_RETRY_CONFIG)
        def contract_func():
            nonlocal call_count
            call_count += 1
            raise ContractCallError("c", "m", "revert")

        with pytest.raises(ContractCallError):
            contract_func()
        assert call_count == 1

    def test_retry_exhausted(self):
        """重试耗尽"""
        call_count = 0

        @retry(config=RetryConfig(max_attempts=2, base_delay=0.01, jitter=False))
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise NetworkError("always fails")

        with pytest.raises(RetryExhaustedError) as exc_info:
            always_fail()

        assert call_count == 2
        assert exc_info.value.last_error is not None


class TestRetryContext:
    """测试重试上下文"""

    def test_success_on_first_try(self):
        """第一次成功"""
        with RetryContext(config=DEFAULT_RETRY_CONFIG, operation="test") as ctx:
            ctx.next_attempt()
            ctx.success()

        assert ctx.attempt == 1
        assert ctx._succeeded is True

    def test_success_after_retry(self):
        """重试后成功"""
        config = RetryConfig(max_attempts=3, base_delay=0.01, jitter=False)
        attempt_results = [NetworkError("fail"), NetworkError("fail"), "ok"]
        idx = 0

        with RetryContext(config=config, operation="test") as ctx:
            while ctx.should_retry():
                ctx.next_attempt()
                result = attempt_results[idx]
                idx += 1
                if isinstance(result, Exception):
                    ctx.failed(result)
                else:
                    ctx.success()
                    break

        assert ctx.attempt == 3
        assert ctx._succeeded is True

    def test_exhausted_raises(self):
        """耗尽时抛出异常"""
        config = RetryConfig(max_attempts=2, base_delay=0.01, jitter=False)

        with pytest.raises(RetryExhaustedError):
            with RetryContext(config=config, operation="test") as ctx:
                while ctx.should_retry():
                    ctx.next_attempt()
                    ctx.failed(NetworkError("always fails"))
