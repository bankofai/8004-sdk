"""测试异常类"""

import pytest
from sdk.exceptions import (
    SDKError,
    ConfigurationError,
    MissingContractAddressError,
    InvalidPrivateKeyError,
    ChainIdResolutionError,
    NetworkError,
    RPCError,
    TimeoutError,
    RetryExhaustedError,
    ContractError,
    ContractCallError,
    ContractFunctionNotFoundError,
    TransactionFailedError,
    InsufficientEnergyError,
    SignatureError,
    InvalidSignatureError,
    SignerNotAvailableError,
    DataError,
    InvalidAddressError,
    InvalidHashError,
    ValidationError,
    RequestHashMismatchError,
)


def test_sdk_error_basic():
    """测试基础 SDK 异常"""
    err = SDKError("test message")
    assert str(err) == "[SDK_ERROR] test message"
    assert err.code == "SDK_ERROR"
    assert err.details is None


def test_sdk_error_with_details():
    """测试带详情的异常"""
    err = SDKError("test", code="CUSTOM", details={"key": "value"})
    assert "[CUSTOM]" in str(err)
    assert "key" in str(err)


def test_missing_contract_address_error():
    """测试合约地址缺失异常"""
    err = MissingContractAddressError("identity")
    assert err.code == "MISSING_CONTRACT_ADDRESS"
    assert "identity" in str(err)


def test_invalid_private_key_error():
    """测试私钥无效异常"""
    err = InvalidPrivateKeyError("too short")
    assert err.code == "INVALID_PRIVATE_KEY"
    assert "too short" in str(err)


def test_chain_id_resolution_error():
    """测试 Chain ID 解析异常"""
    err = ChainIdResolutionError("https://example.com")
    assert err.code == "CHAIN_ID_RESOLUTION_FAILED"


def test_retry_exhausted_error():
    """测试重试耗尽异常"""
    original = ValueError("original error")
    err = RetryExhaustedError("test_op", 3, original)
    assert err.code == "RETRY_EXHAUSTED"
    assert err.last_error == original
    assert "3 attempts" in str(err)


def test_contract_call_error():
    """测试合约调用异常"""
    err = ContractCallError("identity", "register", "revert")
    assert err.code == "CONTRACT_CALL_FAILED"
    assert "identity.register" in str(err)


def test_contract_function_not_found_error():
    """测试合约方法不存在异常"""
    err = ContractFunctionNotFoundError("TContract", "unknownMethod", 2)
    assert err.code == "CONTRACT_FUNCTION_NOT_FOUND"
    assert "unknownMethod" in str(err)
    assert "arity 2" in str(err)


def test_transaction_failed_error():
    """测试交易失败异常"""
    err = TransactionFailedError(tx_id="0x123", reason="out of gas")
    assert err.code == "TRANSACTION_FAILED"
    assert "out of gas" in str(err)


def test_insufficient_energy_error():
    """测试能量不足异常"""
    err = InsufficientEnergyError(required=100000, available=50000)
    assert err.code == "INSUFFICIENT_ENERGY"


def test_invalid_address_error():
    """测试地址无效异常"""
    err = InvalidAddressError("invalid_addr", "20 bytes hex")
    assert err.code == "INVALID_ADDRESS"
    assert "invalid_addr" in str(err)


def test_request_hash_mismatch_error():
    """测试请求哈希不匹配异常"""
    err = RequestHashMismatchError("0xaaa", "0xbbb")
    assert err.code == "REQUEST_HASH_MISMATCH"


def test_exception_inheritance():
    """测试异常继承关系"""
    assert issubclass(ConfigurationError, SDKError)
    assert issubclass(MissingContractAddressError, ConfigurationError)
    assert issubclass(NetworkError, SDKError)
    assert issubclass(RetryExhaustedError, NetworkError)
    assert issubclass(ContractError, SDKError)
    assert issubclass(ContractCallError, ContractError)
    assert issubclass(SignatureError, SDKError)
    assert issubclass(DataError, SDKError)
    assert issubclass(ValidationError, SDKError)
