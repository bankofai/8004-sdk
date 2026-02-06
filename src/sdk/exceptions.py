"""
TRC-8004 SDK 异常定义模块

提供细粒度的异常类型，便于调用方精确处理错误。

Exception Hierarchy:
    SDKError (基类)
    ├── ConfigurationError (配置错误)
    │   ├── MissingContractAddressError
    │   ├── InvalidPrivateKeyError
    │   └── ChainIdResolutionError
    ├── NetworkError (网络错误)
    │   ├── RPCError
    │   ├── TimeoutError
    │   └── RetryExhaustedError
    ├── ContractError (合约错误)
    │   ├── ContractCallError
    │   ├── ContractFunctionNotFoundError
    │   ├── TransactionFailedError
    │   └── InsufficientEnergyError
    ├── SignatureError (签名错误)
    │   ├── InvalidSignatureError
    │   └── SignerNotAvailableError
    ├── DataError (数据错误)
    │   ├── InvalidAddressError
    │   ├── InvalidHashError
    │   ├── SerializationError
    │   └── DataLoadError
    └── ValidationError (验证错误)
        ├── RequestHashMismatchError
        ├── FeedbackAuthExpiredError
        └── FeedbackAuthInvalidError

Example:
    >>> from sdk.exceptions import ContractCallError, RetryExhaustedError
    >>> try:
    ...     sdk.register_agent(...)
    ... except RetryExhaustedError as e:
    ...     print(f"重试耗尽: {e.last_error}")
    ... except ContractCallError as e:
    ...     print(f"合约调用失败: {e.code}")

Note:
    - 所有异常都继承自 SDKError
    - 每个异常都有 code 和 details 属性
    - 可以通过捕获父类异常来处理一类错误
"""

from typing import Optional, Any


class SDKError(Exception):
    """
    SDK 基础异常类。

    所有 SDK 异常的基类，提供统一的错误码和详情机制。

    Attributes:
        code: 错误码字符串，用于程序化处理
        details: 错误详情，可以是任意类型

    Args:
        message: 错误消息
        code: 错误码，默认为 "SDK_ERROR"
        details: 错误详情

    Example:
        >>> raise SDKError("Something went wrong", code="CUSTOM_ERROR", details={"key": "value"})
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.code = code or "SDK_ERROR"
        self.details = details

    def __str__(self) -> str:
        """返回格式化的错误消息。"""
        if self.details:
            return f"[{self.code}] {super().__str__()} - {self.details}"
        return f"[{self.code}] {super().__str__()}"


# ============ 配置相关异常 ============


class ConfigurationError(SDKError):
    """
    配置错误基类。

    当 SDK 配置不正确时抛出。

    Args:
        message: 错误消息
        details: 错误详情
    """

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message, "CONFIGURATION_ERROR", details)


class MissingContractAddressError(ConfigurationError):
    """
    合约地址缺失异常。

    当尝试调用合约但未配置对应地址时抛出。

    Attributes:
        contract_name: 缺失地址的合约名称

    Args:
        contract_name: 合约名称（如 "identity", "validation", "reputation"）

    Example:
        >>> raise MissingContractAddressError("identity")
        # [MISSING_CONTRACT_ADDRESS] Contract address missing for 'identity'
    """

    def __init__(self, contract_name: str) -> None:
        super().__init__(
            f"Contract address missing for '{contract_name}'",
            details={"contract": contract_name}
        )
        self.code = "MISSING_CONTRACT_ADDRESS"


class InvalidPrivateKeyError(ConfigurationError):
    """
    私钥格式无效异常。

    当提供的私钥格式不正确时抛出。

    Args:
        reason: 无效原因描述

    Example:
        >>> raise InvalidPrivateKeyError("Expected 64 hex characters")
    """

    def __init__(self, reason: str = "Invalid format") -> None:
        super().__init__(f"Private key invalid: {reason}")
        self.code = "INVALID_PRIVATE_KEY"


class ChainIdResolutionError(ConfigurationError):
    """
    Chain ID 解析失败异常。

    当无法从 RPC 节点获取 Chain ID 时抛出。

    Args:
        rpc_url: 尝试连接的 RPC URL

    Example:
        >>> raise ChainIdResolutionError("https://nile.trongrid.io")
    """

    def __init__(self, rpc_url: Optional[str] = None) -> None:
        super().__init__(
            "Failed to resolve chain ID from RPC",
            details={"rpc_url": rpc_url}
        )
        self.code = "CHAIN_ID_RESOLUTION_FAILED"


# ============ 网络相关异常 ============


class NetworkError(SDKError):
    """
    网络请求错误基类。

    当网络请求失败时抛出。

    Args:
        message: 错误消息
        details: 错误详情
    """

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message, "NETWORK_ERROR", details)


class RPCError(NetworkError):
    """
    RPC 调用失败异常。

    当区块链 RPC 调用失败时抛出。

    Args:
        message: 错误消息
        rpc_url: RPC 节点 URL
        method: 调用的方法名

    Example:
        >>> raise RPCError("Connection refused", rpc_url="https://...", method="eth_call")
    """

    def __init__(
        self,
        message: str,
        rpc_url: Optional[str] = None,
        method: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            details={"rpc_url": rpc_url, "method": method}
        )
        self.code = "RPC_ERROR"


class TimeoutError(NetworkError):
    """
    请求超时异常。

    当操作超过指定时间未完成时抛出。

    Attributes:
        operation: 超时的操作名称
        timeout_seconds: 超时时间

    Args:
        operation: 操作名称
        timeout_seconds: 超时时间（秒）

    Example:
        >>> raise TimeoutError("validation_request", 30.0)
    """

    def __init__(self, operation: str, timeout_seconds: float) -> None:
        super().__init__(
            f"Operation '{operation}' timed out after {timeout_seconds}s",
            details={"operation": operation, "timeout": timeout_seconds}
        )
        self.code = "TIMEOUT_ERROR"


class RetryExhaustedError(NetworkError):
    """
    重试次数耗尽异常。

    当操作在所有重试尝试后仍然失败时抛出。

    Attributes:
        last_error: 最后一次尝试的异常

    Args:
        operation: 操作名称
        attempts: 尝试次数
        last_error: 最后一次尝试的异常

    Example:
        >>> try:
        ...     sdk.register_agent(...)
        ... except RetryExhaustedError as e:
        ...     print(f"Failed after {e.details['attempts']} attempts")
        ...     print(f"Last error: {e.last_error}")
    """

    def __init__(
        self,
        operation: str,
        attempts: int,
        last_error: Optional[Exception] = None,
    ) -> None:
        super().__init__(
            f"Operation '{operation}' failed after {attempts} attempts",
            details={
                "operation": operation,
                "attempts": attempts,
                "last_error": str(last_error),
            }
        )
        self.code = "RETRY_EXHAUSTED"
        self.last_error = last_error


# ============ 合约相关异常 ============


class ContractError(SDKError):
    """
    合约交互错误基类。

    当与智能合约交互失败时抛出。

    Args:
        message: 错误消息
        details: 错误详情
    """

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message, "CONTRACT_ERROR", details)


class ContractCallError(ContractError):
    """
    合约调用失败异常。

    当合约方法调用失败时抛出。

    Args:
        contract: 合约名称
        method: 方法名
        reason: 失败原因

    Example:
        >>> raise ContractCallError("identity", "register", "revert: already registered")
    """

    def __init__(
        self,
        contract: str,
        method: str,
        reason: Optional[str] = None,
    ) -> None:
        super().__init__(
            f"Contract call failed: {contract}.{method}",
            details={"contract": contract, "method": method, "reason": reason}
        )
        self.code = "CONTRACT_CALL_FAILED"


class ContractFunctionNotFoundError(ContractError):
    """
    合约方法不存在异常。

    当尝试调用不存在的合约方法时抛出。

    Args:
        contract: 合约地址或名称
        method: 方法名
        arity: 参数数量（用于区分重载）

    Example:
        >>> raise ContractFunctionNotFoundError("TContract...", "unknownMethod", 2)
    """

    def __init__(
        self,
        contract: str,
        method: str,
        arity: Optional[int] = None,
    ) -> None:
        msg = f"Function '{method}' not found in contract '{contract}'"
        if arity is not None:
            msg += f" with arity {arity}"
        super().__init__(
            msg,
            details={"contract": contract, "method": method, "arity": arity}
        )
        self.code = "CONTRACT_FUNCTION_NOT_FOUND"


class TransactionFailedError(ContractError):
    """
    交易执行失败异常。

    当链上交易执行失败时抛出。

    Args:
        tx_id: 交易 ID
        reason: 失败原因

    Example:
        >>> raise TransactionFailedError(tx_id="0x123...", reason="out of gas")
    """

    def __init__(
        self,
        tx_id: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> None:
        super().__init__(
            f"Transaction failed: {reason or 'unknown reason'}",
            details={"tx_id": tx_id, "reason": reason}
        )
        self.code = "TRANSACTION_FAILED"


class InsufficientEnergyError(ContractError):
    """
    能量/Gas 不足异常。

    当账户能量或 Gas 不足以执行交易时抛出。

    Args:
        required: 所需能量
        available: 可用能量

    Example:
        >>> raise InsufficientEnergyError(required=100000, available=50000)

    Note:
        在 TRON 网络中，能量 (Energy) 用于执行智能合约。
        在 EVM 网络中，对应的是 Gas。
    """

    def __init__(
        self,
        required: Optional[int] = None,
        available: Optional[int] = None,
    ) -> None:
        super().__init__(
            "Insufficient energy/gas for transaction",
            details={"required": required, "available": available}
        )
        self.code = "INSUFFICIENT_ENERGY"


# ============ 签名相关异常 ============


class SignatureError(SDKError):
    """
    签名相关错误基类。

    当签名操作失败时抛出。

    Args:
        message: 错误消息
        details: 错误详情
    """

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message, "SIGNATURE_ERROR", details)


class InvalidSignatureError(SignatureError):
    """
    签名无效异常。

    当签名验证失败时抛出。

    Args:
        reason: 无效原因

    Example:
        >>> raise InvalidSignatureError("Signature length mismatch")
    """

    def __init__(self, reason: str = "Signature verification failed") -> None:
        super().__init__(reason)
        self.code = "INVALID_SIGNATURE"


class SignerNotAvailableError(SignatureError):
    """
    签名器不可用异常。

    当需要签名但未配置签名器时抛出。

    Args:
        reason: 不可用原因

    Example:
        >>> raise SignerNotAvailableError("Private key not configured")
    """

    def __init__(self, reason: str = "Signer not configured") -> None:
        super().__init__(reason)
        self.code = "SIGNER_NOT_AVAILABLE"


# ============ 数据相关异常 ============


class DataError(SDKError):
    """
    数据处理错误基类。

    当数据格式或内容不正确时抛出。

    Args:
        message: 错误消息
        details: 错误详情
    """

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message, "DATA_ERROR", details)


class InvalidAddressError(DataError):
    """
    地址格式无效异常。

    当提供的区块链地址格式不正确时抛出。

    Args:
        address: 无效的地址
        expected_format: 期望的格式描述

    Example:
        >>> raise InvalidAddressError("invalid_addr", "TRON base58 or 20 bytes hex")
    """

    def __init__(
        self,
        address: str,
        expected_format: str = "20 bytes hex",
    ) -> None:
        super().__init__(
            f"Invalid address format: {address}",
            details={"address": address, "expected": expected_format}
        )
        self.code = "INVALID_ADDRESS"


class InvalidHashError(DataError):
    """
    哈希格式无效异常。

    当提供的哈希值格式不正确时抛出。

    Args:
        value: 无效的哈希值
        expected_length: 期望的字节长度

    Example:
        >>> raise InvalidHashError("0x123", expected_length=32)
    """

    def __init__(self, value: str, expected_length: int = 32) -> None:
        super().__init__(
            f"Invalid hash format, expected {expected_length} bytes",
            details={"value": value[:20] + "..." if len(value) > 20 else value}
        )
        self.code = "INVALID_HASH"


class SerializationError(DataError):
    """
    序列化失败异常。

    当数据序列化或反序列化失败时抛出。

    Args:
        reason: 失败原因

    Example:
        >>> raise SerializationError("Invalid JSON format")
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Serialization failed: {reason}")
        self.code = "SERIALIZATION_ERROR"


class DataLoadError(DataError):
    """
    数据加载失败异常。

    当从 URI 加载数据失败时抛出。

    Args:
        uri: 数据 URI
        reason: 失败原因

    Example:
        >>> raise DataLoadError("ipfs://Qm...", "Gateway timeout")
    """

    def __init__(self, uri: str, reason: Optional[str] = None) -> None:
        super().__init__(
            f"Failed to load data from '{uri}'",
            details={"uri": uri, "reason": reason}
        )
        self.code = "DATA_LOAD_ERROR"


# ============ 验证相关异常 ============


class ValidationError(SDKError):
    """
    验证相关错误基类。

    当验证操作失败时抛出。

    Args:
        message: 错误消息
        details: 错误详情
    """

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message, "VALIDATION_ERROR", details)


class RequestHashMismatchError(ValidationError):
    """
    请求哈希不匹配异常。

    当计算的请求哈希与预期不符时抛出。

    Args:
        expected: 预期的哈希值
        actual: 实际计算的哈希值

    Example:
        >>> raise RequestHashMismatchError("0xaaa...", "0xbbb...")
    """

    def __init__(self, expected: str, actual: str) -> None:
        super().__init__(
            "Request hash mismatch",
            details={"expected": expected, "actual": actual}
        )
        self.code = "REQUEST_HASH_MISMATCH"


class FeedbackAuthExpiredError(ValidationError):
    """
    反馈授权已过期异常。

    当 feedbackAuth 的有效期已过时抛出。

    Args:
        expiry: 授权过期时间（Unix 时间戳）
        current: 当前时间（Unix 时间戳）

    Example:
        >>> raise FeedbackAuthExpiredError(expiry=1700000000, current=1700001000)
    """

    def __init__(self, expiry: int, current: int) -> None:
        super().__init__(
            "Feedback authorization has expired",
            details={"expiry": expiry, "current": current}
        )
        self.code = "FEEDBACK_AUTH_EXPIRED"


class FeedbackAuthInvalidError(ValidationError):
    """
    反馈授权无效异常。

    当 feedbackAuth 格式或签名无效时抛出。

    Args:
        reason: 无效原因

    Example:
        >>> raise FeedbackAuthInvalidError("Invalid signature")
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid feedback authorization: {reason}")
        self.code = "FEEDBACK_AUTH_INVALID"
