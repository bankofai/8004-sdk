"""
TRON-8004 SDK Exceptions Module

Provides fine-grained exception types for precise error handling by callers.

Exception Hierarchy:
    SDKError (Base Class)
    ├── ConfigurationError
    │   ├── MissingContractAddressError
    │   ├── InvalidPrivateKeyError
    │   └── ChainIdResolutionError
    ├── NetworkError
    │   ├── RPCError
    │   ├── TimeoutError
    │   └── RetryExhaustedError
    ├── ContractError
    │   ├── ContractCallError
    │   ├── ContractFunctionNotFoundError
    │   ├── TransactionFailedError
    │   └── InsufficientEnergyError
    ├── SignatureError
    │   ├── InvalidSignatureError
    │   └── SignerNotAvailableError
    ├── DataError
    │   ├── InvalidAddressError
    │   ├── InvalidHashError
    │   ├── SerializationError
    │   └── DataLoadError
    └── ValidationError
        ├── RequestHashMismatchError
        ├── FeedbackAuthExpiredError
        └── FeedbackAuthInvalidError

Example:
    >>> from sdk.exceptions import ContractCallError, RetryExhaustedError
    >>> try:
    ...     sdk.register_agent(...)
    ... except RetryExhaustedError as e:
    ...     print(f"Retry exhausted: {e.last_error}")
    ... except ContractCallError as e:
    ...     print(f"Contract call failed: {e.code}")

Note:
    - All exceptions inherit from SDKError
    - Each exception has code and details attributes
    - Can catch parent exceptions to handle a category of errors
"""

from typing import Optional, Any


class SDKError(Exception):
    """
    SDK Base Exception.

    Base class for all SDK exceptions, providing unified error code and details mechanism.

    Attributes:
        code: Error code string for programmatic handling
        details: Error details, can be any type

    Args:
        message: Error message
        code: Error code, defaults to "SDK_ERROR"
        details: Error details

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
        """Return formatted error message."""
        if self.details:
            return f"[{self.code}] {super().__str__()} - {self.details}"
        return f"[{self.code}] {super().__str__()}"


# ============ Configuration Exceptions ============


class ConfigurationError(SDKError):
    """
    Configuration Error Base Class.

    Raised when SDK configuration is incorrect.

    Args:
        message: Error message
        details: Error details
    """

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message, "CONFIGURATION_ERROR", details)


class MissingContractAddressError(ConfigurationError):
    """
    Missing Contract Address Error.

    Raised when attempting to call a contract but address is not configured.

    Attributes:
        contract_name: Name of the contract with missing address

    Args:
        contract_name: Contract name (e.g., "identity", "validation", "reputation")

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
    Invalid Private Key Error.

    Raised when provided private key format is incorrect.

    Args:
        reason: Reason for invalidity

    Example:
        >>> raise InvalidPrivateKeyError("Expected 64 hex characters")
    """

    def __init__(self, reason: str = "Invalid format") -> None:
        super().__init__(f"Private key invalid: {reason}")
        self.code = "INVALID_PRIVATE_KEY"


class ChainIdResolutionError(ConfigurationError):
    """
    Chain ID Resolution Failed Error.

    Raised when unable to fetch Chain ID from RPC node.

    Args:
        rpc_url: RPC URL attempted

    Example:
        >>> raise ChainIdResolutionError("https://nile.trongrid.io")
    """

    def __init__(self, rpc_url: Optional[str] = None) -> None:
        super().__init__(
            "Failed to resolve chain ID from RPC",
            details={"rpc_url": rpc_url}
        )
        self.code = "CHAIN_ID_RESOLUTION_FAILED"


# ============ Network Exceptions ============


class NetworkError(SDKError):
    """
    Network Request Error Base Class.

    Raised when network request fails.

    Args:
        message: Error message
        details: Error details
    """

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message, "NETWORK_ERROR", details)


class RPCError(NetworkError):
    """
    RPC Call Failed Error.

    Raised when blockchain RPC call fails.

    Args:
        message: Error message
        rpc_url: RPC node URL
        method: Method name called

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
    Request Timeout Error.

    Raised when operation does not complete within specified time.

    Attributes:
        operation: Name of the timed out operation
        timeout_seconds: Timeout duration

    Args:
        operation: Operation name
        timeout_seconds: Timeout in seconds

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
    Retry Exhausted Error.

    Raised when operation fails after all retry attempts.

    Attributes:
        last_error: Exception from the last attempt

    Args:
        operation: Operation name
        attempts: Number of attempts
        last_error: Exception from the last attempt

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


# ============ Contract Exceptions ============


class ContractError(SDKError):
    """
    Contract Interaction Error Base Class.

    Raised when interaction with smart contract fails.

    Args:
        message: Error message
        details: Error details
    """

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message, "CONTRACT_ERROR", details)


class ContractCallError(ContractError):
    """
    Contract Call Failed Error.

    Raised when contract method call fails.

    Args:
        contract: Contract name
        method: Method name
        reason: Failure reason

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
    Contract Function Not Found Error.

    Raised when attempting to call a non-existent contract method.

    Args:
        contract: Contract address or name
        method: Method name
        arity: Number of arguments (to distinguish overloads)

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
    Transaction Execution Failed Error.

    Raised when on-chain transaction execution fails.

    Args:
        tx_id: Transaction ID
        reason: Failure reason

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
    Insufficient Energy/Gas Error.

    Raised when account energy or gas is insufficient to execute transaction.

    Args:
        required: Required energy
        available: Available energy

    Example:
        >>> raise InsufficientEnergyError(required=100000, available=50000)

    Note:
        In TRON network, Energy is used to execute smart contracts.
        In EVM networks, it corresponds to Gas.
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


# ============ Signature Exceptions ============


class SignatureError(SDKError):
    """
    Signature Error Base Class.

    Raised when signature operation fails.

    Args:
        message: Error message
        details: Error details
    """

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message, "SIGNATURE_ERROR", details)


class InvalidSignatureError(SignatureError):
    """
    Invalid Signature Error.

    Raised when signature verification fails.

    Args:
        reason: Invalid reason

    Example:
        >>> raise InvalidSignatureError("Signature length mismatch")
    """

    def __init__(self, reason: str = "Signature verification failed") -> None:
        super().__init__(reason)
        self.code = "INVALID_SIGNATURE"


class SignerNotAvailableError(SignatureError):
    """
    Signer Not Available Error.

    Raised when a signer is required but not configured.

    Args:
        reason: Reason for unavailability

    Example:
        >>> raise SignerNotAvailableError("Private key not configured")
    """

    def __init__(self, reason: str = "Signer not configured") -> None:
        super().__init__(reason)
        self.code = "SIGNER_NOT_AVAILABLE"


# ============ Data Exceptions ============


class DataError(SDKError):
    """
    Data Processing Error Base Class.

    Raised when data format or content is incorrect.

    Args:
        message: Error message
        details: Error details
    """

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message, "DATA_ERROR", details)


class InvalidAddressError(DataError):
    """
    Invalid Address Format Error.

    Raised when provided blockchain address format is incorrect.

    Args:
        address: Invalid address
        expected_format: Description of expected format

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
    Invalid Hash Format Error.

    Raised when provided hash value format is incorrect.

    Args:
        value: Invalid hash value
        expected_length: Expected byte length

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
    Serialization Failed Error.

    Raised when data serialization or deserialization fails.

    Args:
        reason: Failure reason

    Example:
        >>> raise SerializationError("Invalid JSON format")
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Serialization failed: {reason}")
        self.code = "SERIALIZATION_ERROR"


class DataLoadError(DataError):
    """
    Data Load Failed Error.

    Raised when loading data from URI fails.

    Args:
        uri: Data URI
        reason: Failure reason

    Example:
        >>> raise DataLoadError("ipfs://Qm...", "Gateway timeout")
    """

    def __init__(self, uri: str, reason: Optional[str] = None) -> None:
        super().__init__(
            f"Failed to load data from '{uri}'",
            details={"uri": uri, "reason": reason}
        )
        self.code = "DATA_LOAD_ERROR"


# ============ Validation Exceptions ============


class ValidationError(SDKError):
    """
    Validation Error Base Class.

    Raised when validation operation fails.

    Args:
        message: Error message
        details: Error details
    """

    def __init__(self, message: str, details: Optional[Any] = None) -> None:
        super().__init__(message, "VALIDATION_ERROR", details)


class RequestHashMismatchError(ValidationError):
    """
    Request Hash Mismatch Error.

    Raised when calculated request hash does not match expected value.

    Args:
        expected: Expected hash value
        actual: Actually calculated hash value

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
    Feedback Authorization Expired Error.

    Raised when feedbackAuth has expired.

    Args:
        expiry: Authorization expiry time (Unix timestamp)
        current: Current time (Unix timestamp)

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
    Feedback Authorization Invalid Error.

    Raised when feedbackAuth format or signature is invalid.

    Args:
        reason: Invalid reason

    Example:
        >>> raise FeedbackAuthInvalidError("Invalid signature")
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid feedback authorization: {reason}")
        self.code = "FEEDBACK_AUTH_INVALID"
