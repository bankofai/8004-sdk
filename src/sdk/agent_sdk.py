"""
TRC-8004 Agent SDK

提供 Agent 与链上合约交互的统一接口，支持：
- 身份注册与元数据管理 (IdentityRegistry)
- 验证请求与响应 (ValidationRegistry)
- 信誉反馈提交 (ReputationRegistry)
- 签名构建与验证
- 请求构建辅助

Example:
    >>> from sdk import AgentSDK
    >>> sdk = AgentSDK(
    ...     private_key="your_hex_private_key",
    ...     rpc_url="https://nile.trongrid.io",
    ...     network="tron:nile",
    ...     identity_registry="TIdentityAddr",
    ...     validation_registry="TValidationAddr",
    ...     reputation_registry="TReputationAddr",
    ... )
    >>> tx_id = sdk.register_agent(token_uri="https://example.com/agent.json")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

from .contract_adapter import ContractAdapter, DummyContractAdapter, TronContractAdapter
from .exceptions import (
    ChainIdResolutionError,
    ConfigurationError,
    InvalidAddressError,
    InvalidPrivateKeyError,
    NetworkError,
    SignerNotAvailableError,
)
from .retry import RetryConfig, DEFAULT_RETRY_CONFIG, retry
from .signer import Signer, SimpleSigner, TronSigner
from .utils import canonical_json, canonical_json_str, keccak256_hex, keccak256_bytes

logger = logging.getLogger("trc8004.sdk")


def _is_hex_key(value: str) -> bool:
    """检查字符串是否为有效的十六进制私钥"""
    if not value:
        return False
    try:
        bytes.fromhex(value)
        return len(value) in (64, 66)  # 32 bytes, with or without 0x
    except ValueError:
        return False


def _is_hex_string(value: str) -> bool:
    """检查字符串是否为有效的十六进制字符串"""
    if not value:
        return False
    try:
        bytes.fromhex(value)
        return True
    except ValueError:
        return False


@dataclass
class SDKConfig:
    """
    SDK 配置类

    Attributes:
        rpc_url: 区块链 RPC 节点地址
        network: 网络标识 (如 "tron:nile", "tron:mainnet", "evm:1")
        timeout: HTTP 请求超时时间（秒）
        identity_registry: IdentityRegistry 合约地址
        validation_registry: ValidationRegistry 合约地址
        reputation_registry: ReputationRegistry 合约地址
        retry_config: 重试配置
    """

    rpc_url: str = "https://nile.trongrid.io"
    network: str = "tron:nile"
    timeout: int = 10
    identity_registry: Optional[str] = None
    validation_registry: Optional[str] = None
    reputation_registry: Optional[str] = None
    retry_config: RetryConfig = field(default_factory=lambda: DEFAULT_RETRY_CONFIG)


class AgentSDK:
    """
    TRC-8004 Agent SDK 主类

    提供与链上合约交互的统一接口，包括：
    - 身份注册与元数据管理
    - 验证请求与响应
    - 信誉反馈提交
    - 签名构建

    Args:
        private_key: 私钥（十六进制字符串，可带 0x 前缀）
        rpc_url: RPC 节点地址
        network: 网络标识（如 "tron:nile"）
        identity_registry: IdentityRegistry 合约地址
        validation_registry: ValidationRegistry 合约地址
        reputation_registry: ReputationRegistry 合约地址
        fee_limit: 交易费用上限（TRON 特有）
        signer: 自定义签名器（可选）
        contract_adapter: 自定义合约适配器（可选）
        retry_config: 重试配置（可选）

    Raises:
        InvalidPrivateKeyError: 私钥格式无效
        ConfigurationError: 配置错误

    Example:
        >>> sdk = AgentSDK(
        ...     private_key="your_private_key",
        ...     rpc_url="https://nile.trongrid.io",
        ...     network="tron:nile",
        ... )
    """

    def __init__(
        self,
        private_key: Optional[str] = None,
        rpc_url: Optional[str] = None,
        network: Optional[str] = None,
        identity_registry: Optional[str] = None,
        validation_registry: Optional[str] = None,
        reputation_registry: Optional[str] = None,
        identity_registry_abi_path: Optional[str] = None,
        validation_registry_abi_path: Optional[str] = None,
        reputation_registry_abi_path: Optional[str] = None,
        fee_limit: Optional[int] = None,
        signer: Optional[Signer] = None,
        contract_adapter: Optional[ContractAdapter] = None,
        retry_config: Optional[RetryConfig] = None,
    ) -> None:
        # 初始化配置
        self.config = SDKConfig()
        if rpc_url is not None:
            self.config.rpc_url = rpc_url
        if network is not None:
            self.config.network = network
        if identity_registry is not None:
            self.config.identity_registry = identity_registry
        if validation_registry is not None:
            self.config.validation_registry = validation_registry
        if reputation_registry is not None:
            self.config.reputation_registry = reputation_registry
        if retry_config is not None:
            self.config.retry_config = retry_config

        # 初始化签名器
        if signer is None:
            signer = self._create_signer(private_key)
        self.signer = signer

        # 初始化合约适配器
        if contract_adapter is None:
            contract_adapter = self._create_contract_adapter(
                identity_registry_abi_path,
                validation_registry_abi_path,
                reputation_registry_abi_path,
                fee_limit,
            )
        self.contract_adapter = contract_adapter

        logger.info(
            "SDK initialized: network=%s, rpc=%s, signer=%s",
            self.config.network,
            self.config.rpc_url,
            type(self.signer).__name__,
        )

    def _create_signer(self, private_key: Optional[str]) -> Signer:
        """创建签名器"""
        if self.config.network.startswith("tron") and private_key:
            cleaned_key = private_key.replace("0x", "")
            if _is_hex_key(cleaned_key):
                try:
                    return TronSigner(private_key=cleaned_key)
                except Exception as e:
                    raise InvalidPrivateKeyError(str(e)) from e
            else:
                logger.warning("Private key is not hex format, using SimpleSigner")
                return SimpleSigner(private_key=private_key)
        return SimpleSigner(private_key=private_key)

    def _create_contract_adapter(
        self,
        identity_abi_path: Optional[str],
        validation_abi_path: Optional[str],
        reputation_abi_path: Optional[str],
        fee_limit: Optional[int],
    ) -> ContractAdapter:
        """创建合约适配器"""
        if self.config.network.startswith("tron"):
            return TronContractAdapter(
                rpc_url=self.config.rpc_url,
                identity_registry=self.config.identity_registry,
                validation_registry=self.config.validation_registry,
                reputation_registry=self.config.reputation_registry,
                identity_registry_abi_path=identity_abi_path,
                validation_registry_abi_path=validation_abi_path,
                reputation_registry_abi_path=reputation_abi_path,
                fee_limit=fee_limit,
                retry_config=self.config.retry_config,
            )
        return DummyContractAdapter()

    def validation_request(
        self,
        validator_addr: str,
        agent_id: int,
        request_uri: str,
        request_hash: Optional[str] = None,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        发起验证请求

        将执行结果提交到 ValidationRegistry，请求验证者进行验证。

        Args:
            validator_addr: 验证者地址
            agent_id: Agent ID（IdentityRegistry 中的 token ID）
            request_uri: 请求数据 URI（如 ipfs://Qm...）
            request_hash: 请求数据哈希（32 bytes，可选，会自动补零）
            signer: 自定义签名器（可选）

        Returns:
            交易 ID

        Raises:
            ContractCallError: 合约调用失败
            SignerNotAvailableError: 签名器不可用

        Example:
            >>> tx_id = sdk.validation_request(
            ...     validator_addr="TValidator...",
            ...     agent_id=1,
            ...     request_uri="ipfs://QmXxx",
            ...     request_hash="0x" + "aa" * 32,
            ... )
        """
        signer = signer or self.signer
        if signer is None:
            raise SignerNotAvailableError()

        params = [validator_addr, agent_id, request_uri, self._normalize_bytes32(request_hash)]
        logger.debug("validation_request: validator=%s, agent_id=%d", validator_addr, agent_id)
        return self.contract_adapter.send("validation", "validationRequest", params, signer)

    def validation_response(
        self,
        request_hash: str,
        response: int,
        response_uri: Optional[str] = None,
        response_hash: Optional[str] = None,
        tag: Optional[str] = None,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        提交验证响应

        验证者调用此方法提交验证结果。

        Args:
            request_hash: 验证请求哈希（32 bytes）
            response: 验证评分（0-100）
            response_uri: 响应数据 URI（可选）
            response_hash: 响应数据哈希（可选）
            tag: 标签（可选，32 bytes）
            signer: 自定义签名器（可选）

        Returns:
            交易 ID

        Raises:
            ContractCallError: 合约调用失败
        """
        signer = signer or self.signer
        if signer is None:
            raise SignerNotAvailableError()

        params = [
            self._normalize_bytes32(request_hash),
            response,
            response_uri or "",
            self._normalize_bytes32(response_hash),
            self._normalize_bytes32(tag),
        ]
        logger.debug("validation_response: request_hash=%s, response=%d", request_hash[:18], response)
        return self.contract_adapter.send("validation", "validationResponse", params, signer)

    def submit_reputation(
        self,
        agent_id: int,
        score: int,
        tag1: Optional[str] = None,
        tag2: Optional[str] = None,
        fileuri: Optional[str] = None,
        filehash: Optional[str] = None,
        feedback_auth: Optional[str] = None,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        提交信誉反馈

        向 ReputationRegistry 提交对 Agent 的评分反馈。

        Args:
            agent_id: Agent ID
            score: 评分（0-100）
            tag1: 标签1（可选，32 bytes）
            tag2: 标签2（可选，32 bytes）
            fileuri: 反馈文件 URI（可选）
            filehash: 反馈文件哈希（可选）
            feedback_auth: 反馈授权签名（由 Agent 提供）
            signer: 自定义签名器（可选）

        Returns:
            交易 ID

        Raises:
            ContractCallError: 合约调用失败
            FeedbackAuthInvalidError: 反馈授权无效

        Example:
            >>> tx_id = sdk.submit_reputation(
            ...     agent_id=1,
            ...     score=95,
            ...     feedback_auth="0x...",
            ... )
        """
        signer = signer or self.signer
        if signer is None:
            raise SignerNotAvailableError()

        params = [
            agent_id,
            score,
            self._normalize_bytes32(tag1),
            self._normalize_bytes32(tag2),
            fileuri or "",
            self._normalize_bytes32(filehash),
            self._normalize_bytes(feedback_auth),
        ]
        logger.debug("submit_reputation: agent_id=%d, score=%d", agent_id, score)
        return self.contract_adapter.send("reputation", "giveFeedback", params, signer)

    def register_agent(
        self,
        token_uri: Optional[str] = None,
        metadata: Optional[list[dict]] = None,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        注册 Agent

        在 IdentityRegistry 中注册新的 Agent，获得唯一的 Agent ID。

        Args:
            token_uri: Agent 元数据 URI（如 https://example.com/agent.json）
            metadata: 初始元数据列表，格式为 [{"key": "name", "value": "MyAgent"}, ...]
            signer: 自定义签名器（可选）

        Returns:
            交易 ID

        Raises:
            ContractCallError: 合约调用失败

        Example:
            >>> tx_id = sdk.register_agent(
            ...     token_uri="https://example.com/agent.json",
            ...     metadata=[{"key": "name", "value": "MyAgent"}],
            ... )
        """
        signer = signer or self.signer
        if signer is None:
            raise SignerNotAvailableError()

        token_uri = token_uri or ""
        if metadata is not None:
            normalized = self._normalize_metadata_entries(metadata)
            params = [token_uri, normalized]
            logger.debug("register_agent: uri=%s, metadata_count=%d", token_uri, len(normalized))
            return self.contract_adapter.send("identity", "register", params, signer)

        if token_uri:
            params = [token_uri]
        else:
            params = []
        logger.debug("register_agent: uri=%s", token_uri or "(empty)")
        return self.contract_adapter.send("identity", "register", params, signer)

    def update_metadata(
        self,
        agent_id: int,
        key: str,
        value: str | bytes,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        更新 Agent 元数据

        Args:
            agent_id: Agent ID
            key: 元数据键
            value: 元数据值（字符串或字节）
            signer: 自定义签名器（可选）

        Returns:
            交易 ID

        Raises:
            ContractCallError: 合约调用失败
        """
        signer = signer or self.signer
        if signer is None:
            raise SignerNotAvailableError()

        if isinstance(value, str):
            value = value.encode("utf-8")
        params = [agent_id, key, value]
        logger.debug("update_metadata: agent_id=%d, key=%s", agent_id, key)
        return self.contract_adapter.send("identity", "setMetadata", params, signer)


    def build_feedback_auth(
        self,
        agent_id: int,
        client_addr: str,
        index_limit: int,
        expiry: int,
        chain_id: Optional[int],
        identity_registry: str,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        构建反馈授权签名

        生成 EIP-191 格式的反馈授权，允许指定地址提交信誉反馈。

        Args:
            agent_id: Agent ID
            client_addr: 被授权的客户端地址
            index_limit: 反馈索引上限
            expiry: 授权过期时间（Unix 时间戳）
            chain_id: 链 ID（可选，会自动解析）
            identity_registry: IdentityRegistry 合约地址
            signer: 自定义签名器（可选）

        Returns:
            反馈授权签名（0x 前缀的十六进制字符串，224 bytes struct + 65 bytes signature）

        Raises:
            ChainIdResolutionError: 无法解析 Chain ID
            InvalidAddressError: 地址格式无效

        Example:
            >>> auth = sdk.build_feedback_auth(
            ...     agent_id=1,
            ...     client_addr="TClient...",
            ...     index_limit=10,
            ...     expiry=int(time.time()) + 3600,
            ...     chain_id=None,  # 自动解析
            ...     identity_registry="TIdentity...",
            ... )
        """
        signer = signer or self.signer
        if signer is None:
            raise SignerNotAvailableError()

        if chain_id is None:
            chain_id = self.resolve_chain_id()
        if chain_id is None:
            raise ChainIdResolutionError(self.config.rpc_url)

        signer_addr = signer.get_address()

        # 构建 feedbackAuth 结构体
        struct_bytes = b"".join(
            [
                self._abi_encode_uint(agent_id),
                self._abi_encode_address(client_addr),
                self._abi_encode_uint(index_limit),
                self._abi_encode_uint(expiry),
                self._abi_encode_uint(chain_id),
                self._abi_encode_address(identity_registry),
                self._abi_encode_address(signer_addr),
            ]
        )

        # EIP-191 签名
        struct_hash = keccak256_bytes(struct_bytes)
        message = keccak256_bytes(b"\x19Ethereum Signed Message:\n32" + struct_hash)
        signature = self._normalize_bytes(signer.sign_message(message))

        # 规范化签名（处理 v 值和 s 值）
        if len(signature) == 65:
            v = signature[-1]
            if v in (0, 1):
                v += 27
            r = int.from_bytes(signature[:32], byteorder="big")
            s = int.from_bytes(signature[32:64], byteorder="big")
            secp256k1_n = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
            if s > secp256k1_n // 2:
                s = secp256k1_n - s
                v = 27 if v == 28 else 28
            signature = (
                r.to_bytes(32, byteorder="big")
                + s.to_bytes(32, byteorder="big")
                + bytes([v])
            )

        logger.debug("build_feedback_auth: agent_id=%d, client=%s", agent_id, client_addr[:12])
        return "0x" + (struct_bytes + signature).hex()

    @staticmethod
    def _normalize_metadata_entries(entries: list[dict]) -> list[dict]:
        """规范化元数据条目"""
        if not isinstance(entries, list):
            raise TypeError("metadata must be a list of {key,value} objects")
        normalized = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise TypeError("metadata entry must be an object")
            key = entry.get("key")
            value = entry.get("value")
            if not key:
                raise ValueError("metadata entry missing key")
            if isinstance(value, bytes):
                value_bytes = value
            elif isinstance(value, str):
                if value.startswith("0x") and _is_hex_string(value[2:]):
                    value_bytes = bytes.fromhex(value[2:])
                else:
                    value_bytes = value.encode("utf-8")
            elif value is None:
                value_bytes = b""
            else:
                raise TypeError("metadata value must be bytes or string")
            normalized.append({"key": key, "value": value_bytes})
        return normalized

    def resolve_chain_id(self) -> Optional[int]:
        """
        从 RPC 节点解析 Chain ID

        Returns:
            Chain ID，解析失败返回 None
        """
        rpc_url = self.config.rpc_url
        if not rpc_url:
            return None
        url = rpc_url.rstrip("/") + "/jsonrpc"
        try:
            response = httpx.post(
                url,
                json={"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1},
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            result = response.json().get("result")
            if isinstance(result, str) and result.startswith("0x"):
                return int(result, 16)
        except Exception as e:
            logger.warning("Failed to resolve chain ID: %s", e)
            return None
        return None

    def build_commitment(self, order_params: dict) -> str:
        """
        构建订单承诺哈希

        对订单参数进行规范化 JSON 序列化后计算 keccak256 哈希。

        Args:
            order_params: 订单参数字典

        Returns:
            承诺哈希（0x 前缀）

        Example:
            >>> commitment = sdk.build_commitment({
            ...     "asset": "TRX/USDT",
            ...     "amount": 100.0,
            ...     "slippage": 0.01,
            ... })
        """
        payload = canonical_json(order_params)
        return keccak256_hex(payload)

    def compute_request_hash(self, request_payload: str | dict) -> str:
        """
        计算请求数据哈希

        Args:
            request_payload: 请求数据（字典或 JSON 字符串）

        Returns:
            请求哈希（0x 前缀）
        """
        if isinstance(request_payload, dict):
            payload_bytes = canonical_json(request_payload)
        else:
            payload_bytes = str(request_payload).encode("utf-8")
        return keccak256_hex(payload_bytes)

    def dump_canonical(self, payload: dict) -> str:
        """
        规范化 JSON 序列化

        Args:
            payload: 待序列化的字典

        Returns:
            规范化的 JSON 字符串（键排序，无空格）
        """
        return canonical_json_str(payload)

    def build_a2a_signature(
        self,
        action_commitment: str,
        timestamp: int,
        caller_address: str,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        构建 A2A 请求签名

        Args:
            action_commitment: 操作承诺哈希
            timestamp: 时间戳
            caller_address: 调用方地址
            signer: 自定义签名器（可选）

        Returns:
            签名（0x 前缀）
        """
        signer = signer or self.signer
        if signer is None:
            raise SignerNotAvailableError()

        payload = {
            "actionCommitment": action_commitment,
            "timestamp": timestamp,
            "callerAddress": caller_address,
        }
        message = keccak256_bytes(canonical_json(payload))
        return signer.sign_message(message)

    def build_market_order_quote_request(self, asset: str, amount: float, slippage: float = 0.01) -> dict:
        """
        构建市价单报价请求

        Args:
            asset: 交易对（如 "TRX/USDT"）
            amount: 交易数量
            slippage: 滑点容忍度（默认 1%）

        Returns:
            报价请求字典
        """
        return {
            "asset": asset,
            "amount": amount,
            "slippage": slippage,
        }

    def build_market_order_new_request(
        self,
        asset: str,
        amount: float,
        payment_tx_hash: str,
        slippage: float = 0.01,
    ) -> dict:
        """
        构建新建市价单请求

        Args:
            asset: 交易对
            amount: 交易数量
            payment_tx_hash: 支付交易哈希
            slippage: 滑点容忍度

        Returns:
            新建订单请求字典
        """
        return {
            "asset": asset,
            "amount": amount,
            "slippage": slippage,
            "paymentTxHash": payment_tx_hash,
        }

    def build_x402_quote_request(self, order_params: dict) -> dict:
        """
        构建 X402 报价请求

        Args:
            order_params: 订单参数

        Returns:
            X402 报价请求字典
        """
        return {"orderParams": order_params}

    def build_x402_execute_request(
        self,
        action_commitment: str,
        order_params: dict,
        payment_tx_hash: str,
        timestamp: int,
        caller_address: str,
        include_signature: bool = True,
    ) -> dict:
        """
        构建 X402 执行请求

        Args:
            action_commitment: 操作承诺哈希
            order_params: 订单参数
            payment_tx_hash: 支付交易哈希
            timestamp: 时间戳
            caller_address: 调用方地址
            include_signature: 是否包含签名

        Returns:
            X402 执行请求字典
        """
        payload = {
            "actionCommitment": action_commitment,
            "orderParams": order_params,
            "paymentTxHash": payment_tx_hash,
            "timestamp": timestamp,
        }
        if include_signature:
            payload["signature"] = self.build_a2a_signature(
                action_commitment, timestamp, caller_address
            )
        return payload

    def build_payment_signature(
        self,
        action_commitment: str,
        payment_address: str,
        amount: str,
        timestamp: int,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        构建支付签名

        Args:
            action_commitment: 操作承诺哈希
            payment_address: 收款地址
            amount: 支付金额
            timestamp: 时间戳
            signer: 自定义签名器（可选）

        Returns:
            支付签名（0x 前缀）
        """
        signer = signer or self.signer
        if signer is None:
            raise SignerNotAvailableError()

        payload = {
            "actionCommitment": action_commitment,
            "paymentAddress": payment_address,
            "amount": amount,
            "timestamp": timestamp,
        }
        message = keccak256_bytes(canonical_json(payload))
        return signer.sign_message(message)

    @staticmethod
    def _normalize_bytes32(value: Optional[str | bytes]) -> bytes:
        """规范化为 32 字节"""
        if value is None:
            return b"\x00" * 32
        if isinstance(value, bytes):
            if len(value) < 32:
                return value.ljust(32, b"\x00")
            return value[:32]
        cleaned = value[2:] if value.startswith("0x") else value
        if not cleaned:
            return b"\x00" * 32
        raw = bytes.fromhex(cleaned)
        if len(raw) < 32:
            return raw.ljust(32, b"\x00")
        return raw[:32]

    @staticmethod
    def _normalize_bytes(value: Optional[str | bytes]) -> bytes:
        """规范化为字节"""
        if value is None:
            return b""
        if isinstance(value, bytes):
            return value
        cleaned = value[2:] if value.startswith("0x") else value
        if not cleaned:
            return b""
        return bytes.fromhex(cleaned)

    @staticmethod
    def _abi_encode_uint(value: int) -> bytes:
        """ABI 编码无符号整数（32 字节）"""
        return int(value).to_bytes(32, byteorder="big")

    @staticmethod
    def _abi_encode_address(address: str) -> bytes:
        """
        ABI 编码地址（32 字节，左填充零）

        支持 TRON base58 地址和 EVM hex 地址。

        Raises:
            InvalidAddressError: 地址格式无效
        """
        addr = address
        if addr.startswith("T"):
            try:
                from tronpy.keys import to_hex_address
            except Exception as exc:
                raise InvalidAddressError(address, "tronpy required for base58") from exc
            addr = to_hex_address(addr)
        if addr.startswith("0x"):
            addr = addr[2:]
        if len(addr) == 42 and addr.startswith("41"):
            addr = addr[2:]
        if len(addr) != 40:
            raise InvalidAddressError(address, "expected 20 bytes hex")
        return bytes.fromhex(addr).rjust(32, b"\x00")
