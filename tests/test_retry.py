"""Test Retry Mechanism"""

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
    """Test retry configuration"""

    def test_default_config(self):
        """Test default configuration"""
        config = DEFAULT_RETRY_CONFIG
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.jitter is True

    def test_aggressive_config(self):
        """Test aggressive configuration"""
        config = AGGRESSIVE_RETRY_CONFIG
        assert config.max_attempts == 5
        assert config.base_delay == 0.5

    def test_conservative_config(self):
        """Test conservative configuration"""
        config = CONSERVATIVE_RETRY_CONFIG
        assert config.max_attempts == 2
        assert config.base_delay == 2.0

    def test_no_retry_config(self):
        """Test no-retry configuration"""
        config = NO_RETRY_CONFIG
        assert config.max_attempts == 1


class TestCalculateDelay:
    """Test delay calculation"""

    def test_first_attempt_no_delay(self):
        """No delay for the first attempt"""
        config = RetryConfig(base_delay=1.0, jitter=False)
        assert calculate_delay(1, config) == 0.0

    def test_exponential_backoff(self):
        """Test exponential backoff"""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)
        assert calculate_delay(2, config) == 1.0  # 1 * 2^0
        assert calculate_delay(3, config) == 2.0  # 1 * 2^1
        assert calculate_delay(4, config) == 4.0  # 1 * 2^2

    def test_max_delay_cap(self):
        """Test max delay cap"""
        config = RetryConfig(base_delay=1.0, max_delay=5.0, exponential_base=2.0, jitter=False)
        assert calculate_delay(10, config) == 5.0  # Capped at max_delay

    def test_jitter_adds_randomness(self):
        """Test jitter adds randomness"""
        config = RetryConfig(base_delay=1.0, jitter=True, jitter_factor=0.5)
        delays = [calculate_delay(2, config) for _ in range(10)]
        # Should have different values
        assert len(set(delays)) > 1


class TestIsRetryable:
    """Test if retryable"""

    def test_network_error_retryable(self):
        """Network errors are retryable"""
        config = DEFAULT_RETRY_CONFIG
        assert is_retryable(NetworkError("timeout"), config) is True
        assert is_retryable(RPCError("failed"), config) is True

    def test_contract_error_not_retryable(self):
        """Contract errors are not retryable"""
        config = DEFAULT_RETRY_CONFIG
        assert is_retryable(ContractCallError("c", "m", "revert"), config) is False

    def test_connection_error_retryable(self):
        """Connection errors are retryable"""
        config = DEFAULT_RETRY_CONFIG
        assert is_retryable(ConnectionError("refused"), config) is True


class TestRetryDecorator:
    """Test retry decorator"""

    def test_success_no_retry(self):
        """No retry on success"""
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
        """Retry on network error"""
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
        """No retry on contract error"""
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
        """Retries exhausted"""
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
    """Test retry context"""

    def test_success_on_first_try(self):
        """Success on first try"""
        with RetryContext(config=DEFAULT_RETRY_CONFIG, operation="test") as ctx:
            ctx.next_attempt()
            ctx.success()

        assert ctx.attempt == 1
        assert ctx._succeeded is True

    def test_success_after_retry(self):
        """Success after retry"""
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
        """Raises when exhausted"""
        config = RetryConfig(max_attempts=2, base_delay=0.01, jitter=False)

        with pytest.raises(RetryExhaustedError):
            with RetryContext(config=config, operation="test") as ctx:
                while ctx.should_retry():
                    ctx.next_attempt()
                    ctx.failed(NetworkError("always fails"))
