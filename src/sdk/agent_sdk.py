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
        response_uri: str = "",
        response_hash: Optional[str] = None,
        tag: str = "",
        signer: Optional[Signer] = None,
    ) -> str:
        """
        提交验证响应 (Jan 2026 Update)

        验证者调用此方法提交验证结果。

        Args:
            request_hash: 验证请求哈希（32 bytes）
            response: 验证评分（0-100）
            response_uri: 响应数据 URI（可选）
            response_hash: 响应数据哈希（可选）
            tag: 标签（可选，字符串）
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
            response_uri,
            self._normalize_bytes32(response_hash),
            tag,
        ]
        logger.debug("validation_response: request_hash=%s, response=%d", request_hash[:18], response)
        return self.contract_adapter.send("validation", "validationResponse", params, signer)

    def submit_reputation(
        self,
        agent_id: int,
        score: int,
        tag1: str = "",
        tag2: str = "",
        endpoint: str = "",
        feedback_uri: str = "",
        feedback_hash: Optional[str] = None,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        提交信誉反馈 (Jan 2026 Update)

        向 ReputationRegistry 提交对 Agent 的评分反馈。
        
        注意：Jan 2026 更新移除了 feedbackAuth 预授权机制，现在任何人都可以直接提交反馈。
        Spam/Sybil 防护通过链下过滤和信誉系统处理。

        Args:
            agent_id: Agent ID
            score: 评分（0-100）
            tag1: 标签1（可选，字符串）
            tag2: 标签2（可选，字符串）
            endpoint: 使用的 endpoint（可选）
            feedback_uri: 反馈文件 URI（可选）
            feedback_hash: 反馈文件哈希（可选，IPFS 不需要）
            signer: 自定义签名器（可选）

        Returns:
            交易 ID

        Raises:
            ContractCallError: 合约调用失败

        Example:
            >>> tx_id = sdk.submit_reputation(
            ...     agent_id=1,
            ...     score=95,
            ...     tag1="execution",
            ...     tag2="market-swap",
            ...     endpoint="/a2a/x402/execute",
            ... )
        """
        signer = signer or self.signer
        if signer is None:
            raise SignerNotAvailableError()

        params = [
            agent_id,
            score,
            tag1,
            tag2,
            endpoint,
            feedback_uri,
            self._normalize_bytes32(feedback_hash),
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

    @staticmethod
    def extract_metadata_from_card(card: dict) -> list[dict]:
        """
        从 agent-card.json 提取关键信息作为链上 metadata。

        注意：根据 ERC-8004 规范，链上 metadata 应该是最小化的。
        大部分信息应该存储在 token_uri 指向的 registration file 中。
        
        此方法只提取真正需要链上可组合性的字段：
        - name: Agent 名称（便于链上查询）
        - version: 版本号
        
        其他信息（description, skills, endpoints, tags 等）应通过 token_uri 获取。

        Args:
            card: agent-card.json 内容

        Returns:
            metadata 列表，格式为 [{"key": "name", "value": "MyAgent"}, ...]

        Example:
            >>> with open("agent-card.json") as f:
            ...     card = json.load(f)
            >>> metadata = AgentSDK.extract_metadata_from_card(card)
            >>> tx_id = sdk.register_agent(token_uri="https://...", metadata=metadata)
        """
        metadata = []

        # 只提取最关键的字段用于链上查询
        if card.get("name"):
            metadata.append({"key": "name", "value": card["name"]})
        if card.get("version"):
            metadata.append({"key": "version", "value": card["version"]})

        return metadata
    
    @staticmethod
    def extract_full_metadata_from_card(card: dict) -> list[dict]:
        """
        从 agent-card.json 提取完整信息作为链上 metadata。

        警告：这会将大量数据写入链上，增加 gas 成本。
        通常不推荐使用，除非有特殊的链上可组合性需求。
        
        根据 ERC-8004 规范，建议使用 token_uri 指向链下 registration file。

        Args:
            card: agent-card.json 内容

        Returns:
            metadata 列表
        """
        import json as json_module
        metadata = []

        # 基础字段
        if card.get("name"):
            metadata.append({"key": "name", "value": card["name"]})
        if card.get("description"):
            metadata.append({"key": "description", "value": card["description"]})
        if card.get("version"):
            metadata.append({"key": "version", "value": card["version"]})
        if card.get("url"):
            metadata.append({"key": "url", "value": card["url"]})

        # 复杂字段 (JSON 序列化)
        if card.get("skills"):
            skills_summary = [{"id": s.get("id"), "name": s.get("name")} for s in card["skills"]]
            metadata.append({"key": "skills", "value": json_module.dumps(skills_summary, ensure_ascii=False)})

        if card.get("tags"):
            metadata.append({"key": "tags", "value": json_module.dumps(card["tags"], ensure_ascii=False)})

        if card.get("endpoints"):
            endpoints_summary = [{"name": e.get("name"), "endpoint": e.get("endpoint")} for e in card["endpoints"]]
            metadata.append({"key": "endpoints", "value": json_module.dumps(endpoints_summary, ensure_ascii=False)})

        if card.get("capabilities"):
            metadata.append({"key": "capabilities", "value": json_module.dumps(card["capabilities"], ensure_ascii=False)})

        return metadata

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

    def set_agent_wallet(
        self,
        agent_id: int,
        wallet_address: str,
        deadline: int,
        wallet_signer: Optional[Signer] = None,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        设置 Agent 钱包地址（需要 EIP-712 签名验证）(Jan 2026 Update)

        根据 ERC-8004 规范，agentWallet 是保留字段，设置时需要证明调用者控制该钱包。
        此方法会自动生成 EIP-712 格式的钱包所有权证明签名。

        Args:
            agent_id: Agent ID
            wallet_address: 要设置的钱包地址
            deadline: 签名过期时间（Unix 时间戳）
            wallet_signer: 钱包签名器（用于生成所有权证明，默认使用 self.signer）
            signer: 交易签名器（Agent owner，默认使用 self.signer）

        Returns:
            交易 ID

        Raises:
            ContractCallError: 合约调用失败
            SignerNotAvailableError: 签名器不可用

        Example:
            >>> import time
            >>> deadline = int(time.time()) + 3600  # 1 hour from now
            >>> 
            >>> # 设置自己的钱包（signer 同时是 owner 和 wallet）
            >>> tx_id = sdk.set_agent_wallet(
            ...     agent_id=1,
            ...     wallet_address="TWallet...",
            ...     deadline=deadline,
            ... )
            >>> 
            >>> # 设置其他钱包（需要该钱包的签名器）
            >>> wallet_signer = TronSigner(private_key="wallet_private_key")
            >>> tx_id = sdk.set_agent_wallet(
            ...     agent_id=1,
            ...     wallet_address="TWallet...",
            ...     deadline=deadline,
            ...     wallet_signer=wallet_signer,
            ... )
        """
        signer = signer or self.signer
        if signer is None:
            raise SignerNotAvailableError()
        
        wallet_signer = wallet_signer or self.signer
        if wallet_signer is None:
            raise SignerNotAvailableError("Wallet signer required for ownership proof")

        # 构建 EIP-712 钱包所有权证明签名
        signature = self._build_eip712_wallet_signature(
            agent_id=agent_id,
            wallet_address=wallet_address,
            deadline=deadline,
            wallet_signer=wallet_signer,
        )

        params = [agent_id, wallet_address, deadline, signature]
        logger.debug("set_agent_wallet: agent_id=%d, wallet=%s, deadline=%d", agent_id, wallet_address[:12], deadline)
        return self.contract_adapter.send("identity", "setAgentWallet", params, signer)

    def _build_eip712_wallet_signature(
        self,
        agent_id: int,
        wallet_address: str,
        deadline: int,
        wallet_signer: Signer,
    ) -> bytes:
        """
        构建 EIP-712 钱包所有权证明签名 (Jan 2026 Update)

        EIP-712 Domain:
            name: "ERC-8004 IdentityRegistry"
            version: "1.1"
            chainId: <chain_id>
            verifyingContract: <identity_registry>

        TypeHash: SetAgentWallet(uint256 agentId,address newWallet,uint256 deadline)

        Args:
            agent_id: Agent ID
            wallet_address: 钱包地址
            deadline: 签名过期时间
            wallet_signer: 钱包签名器

        Returns:
            签名字节
        """
        chain_id = self.resolve_chain_id()
        if chain_id is None:
            # 默认使用 TRON Nile testnet chain ID
            chain_id = 3448148188
            logger.warning("Could not resolve chain ID, using default: %d", chain_id)

        identity_registry = self.config.identity_registry or ""

        # EIP-712 Domain Separator
        domain_type_hash = keccak256_bytes(
            b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
        )
        domain_separator = keccak256_bytes(b"".join([
            domain_type_hash,
            keccak256_bytes(b"ERC-8004 IdentityRegistry"),
            keccak256_bytes(b"1.1"),
            self._abi_encode_uint(chain_id),
            self._abi_encode_address(identity_registry),
        ]))

        # SetAgentWallet struct hash
        set_agent_wallet_typehash = keccak256_bytes(
            b"SetAgentWallet(uint256 agentId,address newWallet,uint256 deadline)"
        )
        struct_hash = keccak256_bytes(b"".join([
            set_agent_wallet_typehash,
            self._abi_encode_uint(agent_id),
            self._abi_encode_address(wallet_address),
            self._abi_encode_uint(deadline),
        ]))

        # EIP-712 digest
        digest = keccak256_bytes(
            b"\x19\x01" + domain_separator + struct_hash
        )

        # Sign the digest
        signature = self._normalize_bytes(wallet_signer.sign_message(digest))

        # 规范化签名（处理 v 值）
        if len(signature) == 65:
            v = signature[-1]
            if v in (0, 1):
                v += 27
            signature = signature[:64] + bytes([v])

        return signature
    
    def set_agent_uri(
        self,
        agent_id: int,
        new_uri: str,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        更新 Agent 的 URI (Jan 2026 Update)

        更新 Agent 的 registration file URI。只有 owner 或 approved operator 可以调用。

        Args:
            agent_id: Agent ID
            new_uri: 新的 URI
            signer: 自定义签名器（可选）

        Returns:
            交易 ID

        Raises:
            ContractCallError: 合约调用失败
            SignerNotAvailableError: 签名器不可用

        Example:
            >>> tx_id = sdk.set_agent_uri(
            ...     agent_id=1,
            ...     new_uri="https://example.com/new-agent.json",
            ... )
        """
        signer = signer or self.signer
        if signer is None:
            raise SignerNotAvailableError()

        params = [agent_id, new_uri]
        logger.debug("set_agent_uri: agent_id=%d, uri=%s", agent_id, new_uri[:50])
        return self.contract_adapter.send("identity", "setAgentURI", params, signer)

    # ==================== Identity Registry 只读方法 ====================

    def get_agent_uri(self, agent_id: int) -> str:
        """
        获取 Agent 的 tokenURI

        Args:
            agent_id: Agent ID

        Returns:
            Agent 的 tokenURI（指向 registration file）

        Example:
            >>> uri = sdk.get_agent_uri(1)
            >>> print(uri)  # "https://example.com/agent.json"
        """
        params = [agent_id]
        return self.contract_adapter.call("identity", "tokenURI", params)

    def get_metadata(self, agent_id: int, key: str) -> bytes:
        """
        获取 Agent 的链上 metadata

        Args:
            agent_id: Agent ID
            key: metadata 键名

        Returns:
            metadata 值（bytes）

        Example:
            >>> name = sdk.get_metadata(1, "name")
            >>> print(name.decode("utf-8"))  # "MyAgent"
        """
        params = [agent_id, key]
        return self.contract_adapter.call("identity", "getMetadata", params)

    def agent_exists(self, agent_id: int) -> bool:
        """
        检查 Agent 是否存在

        Args:
            agent_id: Agent ID

        Returns:
            是否存在
        """
        params = [agent_id]
        return self.contract_adapter.call("identity", "agentExists", params)

    def get_agent_owner(self, agent_id: int) -> str:
        """
        获取 Agent 的所有者地址

        Args:
            agent_id: Agent ID

        Returns:
            所有者地址
        """
        params = [agent_id]
        return self.contract_adapter.call("identity", "ownerOf", params)

    def total_agents(self) -> int:
        """
        获取已注册的 Agent 总数

        Returns:
            Agent 总数
        """
        return self.contract_adapter.call("identity", "totalAgents", [])

    def get_agent_wallet(self, agent_id: int) -> str:
        """
        获取 Agent 的钱包地址

        Args:
            agent_id: Agent ID

        Returns:
            钱包地址（如果未设置返回零地址）

        Example:
            >>> wallet = sdk.get_agent_wallet(1)
            >>> print(wallet)  # "TWallet..."
        """
        params = [agent_id]
        return self.contract_adapter.call("identity", "getAgentWallet", params)

    # ==================== Validation Registry 只读方法 ====================

    def get_validation_status(self, request_hash: str) -> dict:
        """
        获取验证状态 (Jan 2026 Update)

        Args:
            request_hash: 验证请求哈希（32 bytes）

        Returns:
            验证结果字典，包含:
            - validatorAddress: 验证者地址 (address(0) if no response yet)
            - agentId: Agent ID (0 if no response yet)
            - response: 验证评分 (0-100, or 0 if no response yet)
            - tag: 标签 (string)
            - lastUpdate: 最后更新时间戳 (0 if no response yet)

        Note:
            返回默认值表示请求待处理（无响应），不会抛出异常。
            要区分不存在的请求和待处理的请求，请使用 request_exists()。

        Example:
            >>> result = sdk.get_validation_status("0x" + "aa" * 32)
            >>> print(result["response"])  # 100
        """
        params = [self._normalize_bytes32(request_hash)]
        result = self.contract_adapter.call("validation", "getValidationStatus", params)
        if isinstance(result, (list, tuple)) and len(result) >= 5:
            return {
                "validatorAddress": result[0],
                "agentId": result[1],
                "response": result[2],
                "tag": result[3],
                "lastUpdate": result[4],
            }
        return result

    def get_validation(self, request_hash: str) -> dict:
        """
        获取验证结果 (已弃用，请使用 get_validation_status)

        Args:
            request_hash: 验证请求哈希（32 bytes）

        Returns:
            验证结果字典
        """
        logger.warning("get_validation() is deprecated, use get_validation_status() instead")
        return self.get_validation_status(request_hash)

    def request_exists(self, request_hash: str) -> bool:
        """
        检查验证请求是否存在 (Jan 2026 Update)

        Args:
            request_hash: 验证请求哈希（32 bytes）

        Returns:
            是否存在

        Example:
            >>> exists = sdk.request_exists("0x" + "aa" * 32)
        """
        params = [self._normalize_bytes32(request_hash)]
        return self.contract_adapter.call("validation", "requestExists", params)

    def get_validation_request(self, request_hash: str) -> dict:
        """
        获取验证请求详情 (Jan 2026 Update)

        Args:
            request_hash: 验证请求哈希（32 bytes）

        Returns:
            请求详情字典，包含:
            - validatorAddress: 验证者地址
            - agentId: Agent ID
            - requestURI: 请求 URI
            - timestamp: 请求时间戳

        Example:
            >>> request = sdk.get_validation_request("0x" + "aa" * 32)
            >>> print(request["requestURI"])
        """
        params = [self._normalize_bytes32(request_hash)]
        result = self.contract_adapter.call("validation", "getRequest", params)
        if isinstance(result, (list, tuple)) and len(result) >= 4:
            return {
                "validatorAddress": result[0],
                "agentId": result[1],
                "requestURI": result[2],
                "timestamp": result[3],
            }
        return result

    def get_validation_summary(
        self,
        agent_id: int,
        validator_addresses: Optional[list[str]] = None,
        tag: str = "",
    ) -> dict:
        """
        获取 Agent 的验证汇总 (Jan 2026 Update)

        Args:
            agent_id: Agent ID
            validator_addresses: 验证者地址列表（可选，用于过滤）
            tag: 标签（可选）

        Returns:
            汇总结果字典，包含:
            - count: 验证数量
            - averageResponse: 平均评分

        Example:
            >>> summary = sdk.get_validation_summary(1)
            >>> print(f"Count: {summary['count']}, Avg: {summary['averageResponse']}")
        """
        params = [agent_id, validator_addresses or [], tag]
        result = self.contract_adapter.call("validation", "getSummary", params)
        if isinstance(result, (list, tuple)) and len(result) >= 2:
            return {
                "count": result[0],
                "averageResponse": result[1],
            }
        return result

    def get_agent_validations(self, agent_id: int) -> list[str]:
        """
        获取 Agent 的所有验证请求哈希 (Jan 2026 Update)

        Args:
            agent_id: Agent ID

        Returns:
            请求哈希列表
        """
        params = [agent_id]
        return self.contract_adapter.call("validation", "getAgentValidations", params)

    def get_validator_requests(self, validator_address: str) -> list[str]:
        """
        获取验证者的所有验证请求哈希 (Jan 2026 Update)

        Args:
            validator_address: 验证者地址

        Returns:
            请求哈希列表
        """
        params = [validator_address]
        return self.contract_adapter.call("validation", "getValidatorRequests", params)

    # ==================== Reputation Registry 只读方法 ====================

    def get_feedback_summary(
        self,
        agent_id: int,
        client_addresses: Optional[list[str]] = None,
        tag1: str = "",
        tag2: str = "",
    ) -> dict:
        """
        获取 Agent 的反馈汇总

        Args:
            agent_id: Agent ID
            client_addresses: 客户端地址列表（可选，用于过滤）
            tag1: 标签1（可选）
            tag2: 标签2（可选）

        Returns:
            汇总结果字典，包含:
            - count: 反馈数量
            - averageScore: 平均评分

        Example:
            >>> summary = sdk.get_feedback_summary(1)
            >>> print(f"Count: {summary['count']}, Avg: {summary['averageScore']}")
        """
        params = [agent_id, client_addresses or [], tag1, tag2]
        result = self.contract_adapter.call("reputation", "getSummary", params)
        if isinstance(result, (list, tuple)) and len(result) >= 2:
            return {
                "count": result[0],
                "averageScore": result[1],
            }
        return result

    def read_feedback(
        self,
        agent_id: int,
        client_address: str,
        feedback_index: int,
    ) -> dict:
        """
        读取单条反馈

        Args:
            agent_id: Agent ID
            client_address: 客户端地址
            feedback_index: 反馈索引

        Returns:
            反馈详情字典，包含:
            - score: 评分 (0-100)
            - tag1: 标签1
            - tag2: 标签2
            - isRevoked: 是否已撤销

        Example:
            >>> feedback = sdk.read_feedback(1, "TClient...", 0)
            >>> print(f"Score: {feedback['score']}")
        """
        params = [agent_id, client_address, feedback_index]
        result = self.contract_adapter.call("reputation", "readFeedback", params)
        if isinstance(result, (list, tuple)) and len(result) >= 4:
            return {
                "score": result[0],
                "tag1": result[1],
                "tag2": result[2],
                "isRevoked": result[3],
            }
        return result

    def get_feedback_clients(self, agent_id: int) -> list[str]:
        """
        获取给 Agent 提交过反馈的所有客户端地址

        Args:
            agent_id: Agent ID

        Returns:
            客户端地址列表
        """
        params = [agent_id]
        return self.contract_adapter.call("reputation", "getClients", params)

    def get_last_feedback_index(self, agent_id: int, client_address: str) -> int:
        """
        获取客户端对 Agent 的最后一条反馈索引

        Args:
            agent_id: Agent ID
            client_address: 客户端地址

        Returns:
            最后一条反馈的索引
        """
        params = [agent_id, client_address]
        return self.contract_adapter.call("reputation", "getLastIndex", params)

    # ==================== Reputation Registry 写入方法 ====================

    def revoke_feedback(
        self,
        agent_id: int,
        feedback_index: int,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        撤销反馈

        只有原始提交者可以撤销自己的反馈。

        Args:
            agent_id: Agent ID
            feedback_index: 反馈索引
            signer: 自定义签名器（可选）

        Returns:
            交易 ID

        Example:
            >>> tx_id = sdk.revoke_feedback(agent_id=1, feedback_index=0)
        """
        signer = signer or self.signer
        if signer is None:
            raise SignerNotAvailableError()

        params = [agent_id, feedback_index]
        logger.debug("revoke_feedback: agent_id=%d, index=%d", agent_id, feedback_index)
        return self.contract_adapter.send("reputation", "revokeFeedback", params, signer)

    def append_feedback_response(
        self,
        agent_id: int,
        client_address: str,
        feedback_index: int,
        response_uri: str,
        response_hash: Optional[str] = None,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        追加反馈响应

        任何人都可以追加响应（如 Agent 展示退款证明，或数据分析服务标记垃圾反馈）。

        Args:
            agent_id: Agent ID
            client_address: 原始反馈的客户端地址
            feedback_index: 反馈索引
            response_uri: 响应文件 URI
            response_hash: 响应文件哈希（可选，IPFS URI 不需要）
            signer: 自定义签名器（可选）

        Returns:
            交易 ID

        Example:
            >>> tx_id = sdk.append_feedback_response(
            ...     agent_id=1,
            ...     client_address="TClient...",
            ...     feedback_index=0,
            ...     response_uri="ipfs://Qm...",
            ... )
        """
        signer = signer or self.signer
        if signer is None:
            raise SignerNotAvailableError()

        params = [
            agent_id,
            client_address,
            feedback_index,
            response_uri,
            self._normalize_bytes32(response_hash),
        ]
        logger.debug("append_feedback_response: agent_id=%d, index=%d", agent_id, feedback_index)
        return self.contract_adapter.send("reputation", "appendResponse", params, signer)

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
        构建反馈授权签名 (已弃用 - Jan 2026 Update)

        警告：Jan 2026 更新移除了 feedbackAuth 预授权机制。
        现在任何人都可以直接调用 giveFeedback() 提交反馈，无需预授权。
        此方法保留仅为向后兼容，将在未来版本中移除。

        Args:
            agent_id: Agent ID
            client_addr: 被授权的客户端地址
            index_limit: 反馈索引上限
            expiry: 授权过期时间（Unix 时间戳）
            chain_id: 链 ID（可选，会自动解析）
            identity_registry: IdentityRegistry 合约地址
            signer: 自定义签名器（可选）

        Returns:
            反馈授权签名（0x 前缀的十六进制字符串）

        Raises:
            DeprecationWarning: 此方法已弃用
        """
        import warnings
        warnings.warn(
            "build_feedback_auth() is deprecated since Jan 2026 Update. "
            "feedbackAuth pre-authorization has been removed from the contract. "
            "Use submit_reputation() directly without feedbackAuth.",
            DeprecationWarning,
            stacklevel=2,
        )
        
        signer = signer or self.signer
        if signer is None:
            raise SignerNotAvailableError()

        if chain_id is None:
            chain_id = self.resolve_chain_id()
        if chain_id is None:
            raise ChainIdResolutionError(self.config.rpc_url)

        signer_addr = signer.get_address()

        # 构建 feedbackAuth 结构体 (legacy format)
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

        logger.debug("build_feedback_auth (DEPRECATED): agent_id=%d, client=%s", agent_id, client_addr[:12])
        return "0x" + (struct_bytes + signature).hex()

    @staticmethod
    def _normalize_metadata_entries(entries: list[dict]) -> list[tuple]:
        """
        规范化元数据条目为 tuple 格式 (Jan 2026 Update)
        
        合约期望的格式是 (string metadataKey, bytes metadataValue) 的 tuple 数组
        
        注意：Jan 2026 更新将 struct 字段名从 (key, value) 改为 (metadataKey, metadataValue)
        """
        if not isinstance(entries, list):
            raise TypeError("metadata must be a list of {key,value} objects")
        normalized = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise TypeError("metadata entry must be an object")
            # 支持新旧两种字段名
            key = entry.get("metadataKey") or entry.get("key")
            value = entry.get("metadataValue") or entry.get("value")
            if not key:
                raise ValueError("metadata entry missing key (metadataKey or key)")
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
            # 返回 tuple 格式，符合 Solidity struct 编码要求
            # 字段名为 (metadataKey, metadataValue) 但 tuple 编码只需要值
            normalized.append((key, value_bytes))
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
