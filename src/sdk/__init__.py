"""
TRC-8004 Agent SDK

去中心化 Agent 协作的 Python SDK，支持：
- 身份注册与元数据管理 (IdentityRegistry)
- 验证请求与响应 (ValidationRegistry)
- 信誉反馈提交 (ReputationRegistry)
- A2A 协议客户端

Quick Start:
    >>> from sdk import AgentSDK
    >>> sdk = AgentSDK(
    ...     private_key="your_hex_private_key",
    ...     rpc_url="https://nile.trongrid.io",
    ...     network="tron:nile",
    ... )
    >>> tx_id = sdk.register_agent(token_uri="https://example.com/agent.json")
"""

from .agent_sdk import AgentSDK, SDKConfig
from .contract_adapter import ContractAdapter, DummyContractAdapter, TronContractAdapter
from .signer import Signer, SimpleSigner, TronSigner
from .exceptions import (
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
    SerializationError,
    DataLoadError,
    ValidationError,
    RequestHashMismatchError,
    FeedbackAuthExpiredError,
    FeedbackAuthInvalidError,
)
from .retry import (
    RetryConfig,
    DEFAULT_RETRY_CONFIG,
    AGGRESSIVE_RETRY_CONFIG,
    CONSERVATIVE_RETRY_CONFIG,
    NO_RETRY_CONFIG,
    retry,
    retry_async,
    RetryContext,
)
from .client import AgentClient
from .agent_protocol_client import AgentProtocolClient
from .chain_utils import fetch_event_logs, fetch_trongrid_events, load_request_data, normalize_hash

__version__ = "0.1.0"

__all__ = [
    # Core
    "AgentSDK",
    "SDKConfig",
    # Adapters
    "ContractAdapter",
    "DummyContractAdapter",
    "TronContractAdapter",
    # Signers
    "Signer",
    "SimpleSigner",
    "TronSigner",
    # Exceptions
    "SDKError",
    "ConfigurationError",
    "MissingContractAddressError",
    "InvalidPrivateKeyError",
    "ChainIdResolutionError",
    "NetworkError",
    "RPCError",
    "TimeoutError",
    "RetryExhaustedError",
    "ContractError",
    "ContractCallError",
    "ContractFunctionNotFoundError",
    "TransactionFailedError",
    "InsufficientEnergyError",
    "SignatureError",
    "InvalidSignatureError",
    "SignerNotAvailableError",
    "DataError",
    "InvalidAddressError",
    "InvalidHashError",
    "SerializationError",
    "DataLoadError",
    "ValidationError",
    "RequestHashMismatchError",
    "FeedbackAuthExpiredError",
    "FeedbackAuthInvalidError",
    # Retry
    "RetryConfig",
    "DEFAULT_RETRY_CONFIG",
    "AGGRESSIVE_RETRY_CONFIG",
    "CONSERVATIVE_RETRY_CONFIG",
    "NO_RETRY_CONFIG",
    "retry",
    "retry_async",
    "RetryContext",
    # Clients
    "AgentClient",
    "AgentProtocolClient",
    # Utils
    "fetch_event_logs",
    "fetch_trongrid_events",
    "load_request_data",
    "normalize_hash",
]
