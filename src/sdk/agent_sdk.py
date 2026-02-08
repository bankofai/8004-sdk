"""
TRON-8004 Agent SDK

Provides a unified interface for Agent interactions with on-chain contracts, supporting:
- Identity Registration and Metadata Management (IdentityRegistry)
- Validation Request and Response (ValidationRegistry)
- Reputation Feedback Submission (ReputationRegistry)
- Signature Construction and Verification
- Request Construction Helpers

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
import time
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

logger = logging.getLogger("tron8004.sdk")


def _is_hex_key(value: str) -> bool:
    """Check if string is a valid hexadecimal private key."""
    if not value:
        return False
    try:
        bytes.fromhex(value)
        return len(value) in (64, 66)  # 32 bytes, with or without 0x
    except ValueError:
        return False


def _is_hex_string(value: str) -> bool:
    """Check if string is a valid hexadecimal string."""
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
    SDK Configuration Class.

    Attributes:
        rpc_url: Blockchain RPC node URL
        network: Network identifier (e.g., "tron:nile", "tron:mainnet", "evm:1")
        timeout: HTTP request timeout (seconds)
        identity_registry: IdentityRegistry contract address
        validation_registry: ValidationRegistry contract address
        reputation_registry: ReputationRegistry contract address
        retry_config: Retry configuration
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
    TRON-8004 Agent SDK Main Class.

    Provides a unified interface for interacting with on-chain contracts, including:
    - Identity Registration and Metadata Management
    - Validation Request and Response
    - Reputation Feedback Submission
    - Signature Construction

    Args:
        private_key: Private key (hex string, optional 0x prefix)
        rpc_url: RPC node URL
        network: Network identifier (e.g., "tron:nile")
        identity_registry: IdentityRegistry contract address
        validation_registry: ValidationRegistry contract address
        reputation_registry: ReputationRegistry contract address
        fee_limit: Transaction fee limit (TRON specific)
        signer: Custom signer (optional)
        contract_adapter: Custom contract adapter (optional)
        retry_config: Retry configuration (optional)

    Raises:
        InvalidPrivateKeyError: Invalid private key format
        ConfigurationError: Configuration error

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
        # Initialize configuration
        self.config = SDKConfig()
        if rpc_url is not None:
            self.config.rpc_url = rpc_url
        if network is not None:
            normalized = network
            if normalized in ("nile", "mainnet", "shasta"):
                normalized = f"tron:{normalized}"
            self.config.network = normalized
        if identity_registry is not None:
            self.config.identity_registry = identity_registry
        if validation_registry is not None:
            self.config.validation_registry = validation_registry
        if reputation_registry is not None:
            self.config.reputation_registry = reputation_registry
        if retry_config is not None:
            self.config.retry_config = retry_config

        # Initialize signer
        if signer is None:
            signer = self._create_signer(private_key)
        self.signer = signer

        # Initialize contract adapter
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

    @property
    def address(self) -> Optional[str]:
        """
        Get the signer's address.
        
        Returns:
            Signer address, or None if no signer
        """
        if self.signer is None:
            return None
        return self.signer.get_address()

    def _create_signer(self, private_key: Optional[str]) -> Signer:
        """Create signer."""
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
        """Create contract adapter."""
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
        Initate validation request.

        Submits execution results to ValidationRegistry, requesting validation from a validator.

        Args:
            validator_addr: Validator address
            agent_id: Agent ID (token ID in IdentityRegistry)
            request_uri: Request data URI (e.g., ipfs://Qm...)
            request_hash: Request data hash (32 bytes, optional, auto-padded)
            signer: Custom signer (optional)

        Returns:
            Transaction ID

        Raises:
            ContractCallError: Contract call failed
            SignerNotAvailableError: Signer not available

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
        Submit validation response (Jan 2026 Update).

        Validator calls this method to submit validation results.

        Args:
            request_hash: Validation request hash (32 bytes)
            response: Validation score (0-100)
            response_uri: Response data URI (optional)
            response_hash: Response data hash (optional)
            tag: Tag (optional, string)
            signer: Custom signer (optional)

        Returns:
            Transaction ID

        Raises:
            ContractCallError: Contract call failed
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
        value: Optional[int] = None,
        value_decimals: Optional[int] = None,
        *,
        score: Optional[int] = None,
        tag1: str = "",
        tag2: str = "",
        endpoint: str = "",
        feedback_uri: str = "",
        feedback_hash: Optional[str] = None,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        Submit reputation feedback (Upgradeable).

        Upgradeable contract uses (value, valueDecimals) instead of score.
        For backward compatibility, you may pass score=... and omit value/value_decimals.
        """
        signer = signer or self.signer
        if signer is None:
            raise SignerNotAvailableError()

        if value is None:
            if score is None:
                raise ValueError("value or score is required")
            value = score
        if value_decimals is None:
            value_decimals = 0

        params = [
            agent_id,
            int(value),
            int(value_decimals),
            tag1,
            tag2,
            endpoint,
            feedback_uri,
            self._normalize_bytes32(feedback_hash),
        ]
        logger.debug(
            "submit_reputation: agent_id=%d, value=%d, decimals=%d",
            agent_id,
            value,
            value_decimals,
        )
        return self.contract_adapter.send("reputation", "giveFeedback", params, signer)

    def register_agent(
        self,
        token_uri: Optional[str] = None,
        metadata: Optional[list[dict]] = None,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        Register Agent.

        Registers a new Agent in IdentityRegistry and obtains a unique Agent ID.

        Args:
            token_uri: Agent metadata URI (e.g., https://example.com/agent.json)
            metadata: Initial metadata list, format [{"key": "name", "value": "MyAgent"}, ...]
            signer: Custom signer (optional)

        Returns:
            Transaction ID

        Raises:
            ContractCallError: Contract call failed

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
        Extract key information from agent-card.json as on-chain metadata.

        Note: According to ERC-8004 specification, on-chain metadata should be minimal.
        Most information should be stored in the registration file pointed to by token_uri.
        
        This method only extracts fields truly needed for on-chain composability:
        - name: Agent name (for on-chain queries)
        - version: Version number
        
        Other information (description, skills, endpoints, tags, etc.) should be retrieved via token_uri.

        Args:
            card: agent-card.json content

        Returns:
            Metadata list, format [{"key": "name", "value": "MyAgent"}, ...]

        Example:
            >>> with open("agent-card.json") as f:
            ...     card = json.load(f)
            >>> metadata = AgentSDK.extract_metadata_from_card(card)
            >>> tx_id = sdk.register_agent(token_uri="https://...", metadata=metadata)
        """
        metadata = []

        # Only extract most critical fields for on-chain query
        if card.get("name"):
            metadata.append({"key": "name", "value": card["name"]})
        if card.get("version"):
            metadata.append({"key": "version", "value": card["version"]})

        return metadata
    
    @staticmethod
    def extract_full_metadata_from_card(card: dict) -> list[dict]:
        """
        Extract full information from agent-card.json as on-chain metadata.

        Warning: This will write a large amount of data on-chain, increasing gas costs.
        Generally not recommended unless there are specific on-chain composability requirements.
        
        According to ERC-8004 specification, it is recommended to use token_uri pointing to an off-chain registration file.

        Args:
            card: agent-card.json content

        Returns:
            Metadata list
        """
        import json as json_module
        metadata = []

        # Basic fields
        if card.get("name"):
            metadata.append({"key": "name", "value": card["name"]})
        if card.get("description"):
            metadata.append({"key": "description", "value": card["description"]})
        if card.get("version"):
            metadata.append({"key": "version", "value": card["version"]})
        if card.get("url"):
            metadata.append({"key": "url", "value": card["url"]})

        # Complex fields (JSON serialization)
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
        Update Agent metadata.

        Args:
            agent_id: Agent ID
            key: Metadata key
            value: Metadata value (string or bytes)
            signer: Custom signer (optional)

        Returns:
            Transaction ID

        Raises:
            ContractCallError: Contract call failed
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
        Set Agent wallet address (requires EIP-712 signature verification) (Jan 2026 Update).

        According to ERC-8004 specification, agentWallet is a reserved field. Setting it requires proving that the caller controls the wallet.
        This method automatically generates an EIP-712 formatted wallet ownership proof signature.

        Args:
            agent_id: Agent ID
            wallet_address: Wallet address to set
            deadline: Signature expiration time (Unix timestamp)
            wallet_signer: Wallet signer (used to generate ownership proof, defaults to self.signer)
            signer: Transaction signer (Agent owner, defaults to self.signer)

        Returns:
            Transaction ID

        Raises:
            ContractCallError: Contract call failed
            SignerNotAvailableError: Signer not available

        Example:
            >>> import time
            >>> deadline = int(time.time()) + 300  # within 5 minutes
            >>> 
            >>> # Set own wallet (signer is both owner and wallet)
            >>> tx_id = sdk.set_agent_wallet(
            ...     agent_id=1,
            ...     wallet_address="TWallet...",
            ...     deadline=deadline,
            ... )
            >>> 
            >>> # Set other wallet (requires that wallet's signer)
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

        # Enforce upgradeable contract deadline constraint (<= 5 minutes)
        now = int(time.time())
        if deadline > now + 300:
            raise ValueError("deadline too far: must be within 5 minutes")

        # Build EIP-712 wallet ownership proof signature
        owner_address = signer.get_address()
        signature = self._build_eip712_wallet_signature(
            agent_id=agent_id,
            wallet_address=wallet_address,
            owner_address=owner_address,
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
        owner_address: str,
        deadline: int,
        wallet_signer: Signer,
    ) -> bytes:
        """
        Build EIP-712 wallet ownership proof signature (Jan 2026 Update).

        EIP-712 Domain (Upgradeable):
            name: "ERC8004IdentityRegistry"
            version: "1"
            chainId: <chain_id>
            verifyingContract: <identity_registry>

        TypeHash: AgentWalletSet(uint256 agentId,address newWallet,address owner,uint256 deadline)

        Args:
            agent_id: Agent ID
            wallet_address: Wallet address
            owner_address: Agent owner address (signer address)
            deadline: Signature expiration
            wallet_signer: Wallet signer

        Returns:
            Signature bytes
        """
        chain_id = self.resolve_chain_id()
        if chain_id is None:
            # Default to TRON Nile testnet chain ID
            chain_id = 3448148188
            logger.warning("Could not resolve chain ID, using default: %d", chain_id)

        identity_registry = self.config.identity_registry or ""

        # EIP-712 Domain Separator (Upgradeable)
        domain_type_hash = keccak256_bytes(
            b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
        )
        domain_separator = keccak256_bytes(b"".join([
            domain_type_hash,
            keccak256_bytes(b"ERC8004IdentityRegistry"),
            keccak256_bytes(b"1"),
            self._abi_encode_uint(chain_id),
            self._abi_encode_address(identity_registry),
        ]))

        # AgentWalletSet struct hash (Upgradeable)
        set_agent_wallet_typehash = keccak256_bytes(
            b"AgentWalletSet(uint256 agentId,address newWallet,address owner,uint256 deadline)"
        )
        struct_hash = keccak256_bytes(b"".join([
            set_agent_wallet_typehash,
            self._abi_encode_uint(agent_id),
            self._abi_encode_address(wallet_address),
            self._abi_encode_address(owner_address),
            self._abi_encode_uint(deadline),
        ]))

        # EIP-712 digest
        digest = keccak256_bytes(
            b"\x19\x01" + domain_separator + struct_hash
        )

        # Sign the digest
        signature = self._normalize_bytes(wallet_signer.sign_message(digest))

        # Normalize signature (handle v value)
        if len(signature) == 65:
            v = signature[-1]
            if v in (0, 1):
                v += 27
            signature = signature[:64] + bytes([v])

        return signature

    def unset_agent_wallet(
        self,
        agent_id: int,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        Clear agentWallet (Upgradeable).

        Args:
            agent_id: Agent ID
            signer: Custom signer (optional)

        Returns:
            Transaction ID
        """
        signer = signer or self.signer
        if signer is None:
            raise SignerNotAvailableError()
        params = [agent_id]
        logger.debug("unset_agent_wallet: agent_id=%d", agent_id)
        return self.contract_adapter.send("identity", "unsetAgentWallet", params, signer)
    
    def set_agent_uri(
        self,
        agent_id: int,
        new_uri: str,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        Update Agent URI (Jan 2026 Update).

        Update Agent's registration file URI. Only owner or approved operator can call.

        Args:
            agent_id: Agent ID
            new_uri: New URI
            signer: Custom signer (optional)

        Returns:
            Transaction ID

        Raises:
            ContractCallError: Contract call failed
            SignerNotAvailableError: Signer not available

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

    # ==================== Identity Registry Read-Only Methods ====================

    def get_agent_uri(self, agent_id: int) -> str:
        """
        Get Agent's tokenURI.

        Args:
            agent_id: Agent ID

        Returns:
            Agent's tokenURI (pointing to registration file)

        Example:
            >>> uri = sdk.get_agent_uri(1)
            >>> print(uri)  # "https://example.com/agent.json"
        """
        params = [agent_id]
        return self.contract_adapter.call("identity", "tokenURI", params)

    def get_metadata(self, agent_id: int, key: str) -> bytes:
        """
        Get Agent's on-chain metadata.

        Args:
            agent_id: Agent ID
            key: Metadata key name

        Returns:
            Metadata value (bytes)

        Example:
            >>> name = sdk.get_metadata(1, "name")
            >>> print(name.decode("utf-8"))  # "MyAgent"
        """
        params = [agent_id, key]
        return self.contract_adapter.call("identity", "getMetadata", params)

    def agent_exists(self, agent_id: int) -> bool:
        """
        Check if Agent exists.

        Args:
            agent_id: Agent ID

        Returns:
            True if exists, False otherwise
        """
        params = [agent_id]
        return self.contract_adapter.call("identity", "agentExists", params)

    def get_agent_owner(self, agent_id: int) -> str:
        """
        Get Agent's owner address.

        Args:
            agent_id: Agent ID

        Returns:
            Owner address
        """
        params = [agent_id]
        return self.contract_adapter.call("identity", "ownerOf", params)

    def total_agents(self) -> int:
        """
        Get total number of registered Agents.

        Returns:
            Total Agents count
        """
        return self.contract_adapter.call("identity", "totalAgents", [])

    def get_agent_wallet(self, agent_id: int) -> str:
        """
        Get Agent's wallet address.

        Args:
            agent_id: Agent ID

        Returns:
            Wallet address (returns zero address if not set)

        Example:
            >>> wallet = sdk.get_agent_wallet(1)
            >>> print(wallet)  # "TWallet..."
        """
        params = [agent_id]
        return self.contract_adapter.call("identity", "getAgentWallet", params)

    # ==================== Validation Registry Read-Only Methods ====================

    def get_validation_status(self, request_hash: str) -> dict:
        """
        Get validation status (Jan 2026 Update).

        Args:
            request_hash: Validation request hash (32 bytes)

        Returns:
            Validation result dictionary, containing:
            - validatorAddress
            - agentId
            - response
            - responseHash
            - tag
            - lastUpdate

        Note:
            Upgradeable contract reverts if requestHash is unknown.

        Example:
            >>> result = sdk.get_validation_status("0x" + "aa" * 32)
            >>> print(result["response"])  # 100
        """
        params = [self._normalize_bytes32(request_hash)]
        result = self.contract_adapter.call("validation", "getValidationStatus", params)
        if isinstance(result, (list, tuple)) and len(result) >= 6:
            return {
                "validatorAddress": result[0],
                "agentId": result[1],
                "response": result[2],
                "responseHash": result[3],
                "tag": result[4],
                "lastUpdate": result[5],
            }
        return result

    def get_validation(self, request_hash: str) -> dict:
        """
        Get validation result (Deprecated, use get_validation_status).

        Args:
            request_hash: Validation request hash (32 bytes)

        Returns:
            Validation result dictionary
        """
        logger.warning("get_validation() is deprecated, use get_validation_status() instead")
        return self.get_validation_status(request_hash)

    def request_exists(self, request_hash: str) -> bool:
        """
        Upgradeable ValidationRegistry does NOT support requestExists.
        """
        raise NotImplementedError("request_exists is not supported by upgradeable ValidationRegistry")

    def get_validation_request(self, request_hash: str) -> dict:
        """
        Upgradeable ValidationRegistry does NOT support getRequest.
        """
        raise NotImplementedError("get_validation_request is not supported by upgradeable ValidationRegistry")

    def get_validation_summary(
        self,
        agent_id: int,
        validator_addresses: Optional[list[str]] = None,
        tag: str = "",
    ) -> dict:
        """
        Get Agent's validation summary (Jan 2026 Update).

        Args:
            agent_id: Agent ID
            validator_addresses: Validator address list (optional, for filtering)
            tag: Tag (optional)

        Returns:
            Summary result dictionary, containing:
            - count: Validation count
            - averageResponse: Average score

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
        Get all validation request hashes for an Agent (Jan 2026 Update).

        Args:
            agent_id: Agent ID

        Returns:
            List of request hashes
        """
        params = [agent_id]
        return self.contract_adapter.call("validation", "getAgentValidations", params)

    def get_validator_requests(self, validator_address: str) -> list[str]:
        """
        Get all validation request hashes for a validator (Jan 2026 Update).

        Args:
            validator_address: Validator address

        Returns:
            List of request hashes
        """
        params = [validator_address]
        return self.contract_adapter.call("validation", "getValidatorRequests", params)

    # ==================== Reputation Registry Read-Only Methods ====================

    def get_feedback_summary(
        self,
        agent_id: int,
        client_addresses: Optional[list[str]] = None,
        tag1: str = "",
        tag2: str = "",
    ) -> dict:
        """
        Get Agent's feedback summary.

        Args:
            agent_id: Agent ID
            client_addresses: Client address list (optional, for filtering)
            tag1: Tag 1 (optional)
            tag2: Tag 2 (optional)

        Returns:
            Summary result dictionary, containing:
            - count
            - summaryValue
            - summaryValueDecimals

        Example:
            >>> summary = sdk.get_feedback_summary(1)
            >>> print(f"Count: {summary['count']}, Avg: {summary['averageScore']}")
        """
        if not client_addresses:
            raise ValueError("client_addresses is required for upgradeable ReputationRegistry")
        params = [agent_id, client_addresses, tag1, tag2]
        result = self.contract_adapter.call("reputation", "getSummary", params)
        if isinstance(result, (list, tuple)) and len(result) >= 3:
            return {
                "count": result[0],
                "summaryValue": result[1],
                "summaryValueDecimals": result[2],
            }
        return result

    def read_feedback(
        self,
        agent_id: int,
        client_address: str,
        feedback_index: int,
    ) -> dict:
        """
        Read a single feedback.

        Args:
            agent_id: Agent ID
            client_address: Client address
            feedback_index: Feedback index

        Returns:
            Feedback details dictionary, containing:
            - value
            - valueDecimals
            - tag1
            - tag2
            - isRevoked

        Example:
            >>> feedback = sdk.read_feedback(1, "TClient...", 0)
            >>> print(f"Score: {feedback['score']}")
        """
        params = [agent_id, client_address, feedback_index]
        result = self.contract_adapter.call("reputation", "readFeedback", params)
        if isinstance(result, (list, tuple)) and len(result) >= 5:
            return {
                "value": result[0],
                "valueDecimals": result[1],
                "tag1": result[2],
                "tag2": result[3],
                "isRevoked": result[4],
            }
        return result

    def get_feedback_clients(self, agent_id: int) -> list[str]:
        """
        Get all client addresses that have submitted feedback for an Agent.

        Args:
            agent_id: Agent ID

        Returns:
            List of client addresses
        """
        params = [agent_id]
        return self.contract_adapter.call("reputation", "getClients", params)

    def get_last_feedback_index(self, agent_id: int, client_address: str) -> int:
        """
        Get the index of the last feedback from a client for an Agent.

        Args:
            agent_id: Agent ID
            client_address: Client address

        Returns:
            Index of the last feedback
        """
        params = [agent_id, client_address]
        return self.contract_adapter.call("reputation", "getLastIndex", params)

    # ==================== Reputation Registry Write Methods ====================

    def revoke_feedback(
        self,
        agent_id: int,
        feedback_index: int,
        signer: Optional[Signer] = None,
    ) -> str:
        """
        Revoke feedback.

        Only the original submitter can revoke their own feedback.

        Args:
            agent_id: Agent ID
            feedback_index: Feedback index
            signer: Custom signer (optional)

        Returns:
            Transaction ID

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
        Append feedback response.

        Anyone can append a response (e.g., Agent showing refund proof, or data analysis service flagging spam).

        Args:
            agent_id: Agent ID
            client_address: Client address of original feedback
            feedback_index: Feedback index
            response_uri: Response file URI
            response_hash: Response file hash (optional, not needed for IPFS URI)
            signer: Custom signer (optional)

        Returns:
            Transaction ID

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
        Build feedback authorization signature (Deprecated - Jan 2026 Update).

        Warning: Jan 2026 Update removed feedbackAuth pre-authorization mechanism.
        Now anyone can directly call giveFeedback() to submit feedback without pre-authorization.
        This method is kept only for backward compatibility and will be removed in future versions.

        Args:
            agent_id: Agent ID
            client_addr: Authorized client address
            index_limit: Feedback index limit
            expiry: Authorization expiration (Unix timestamp)
            chain_id: Chain ID (optional, auto-resolved)
            identity_registry: IdentityRegistry contract address
            signer: Custom signer (optional)

        Returns:
            Feedback authorization signature (0x prefixed hex string)

        Raises:
            DeprecationWarning: This method is deprecated
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

        # Build feedbackAuth struct (legacy format)
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

        # EIP-191 Signature
        struct_hash = keccak256_bytes(struct_bytes)
        message = keccak256_bytes(b"\x19Ethereum Signed Message:\n32" + struct_hash)
        signature = self._normalize_bytes(signer.sign_message(message))

        # Normalize signature (handle v and s values)
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
        Normalize metadata entries to tuple format (Jan 2026 Update).
        
        The format expected by the contract is a tuple array of (string metadataKey, bytes metadataValue).
        
        Note: Jan 2026 Update changed struct field names from (key, value) to (metadataKey, metadataValue).
        """
        if not isinstance(entries, list):
            raise TypeError("metadata must be a list of {key,value} objects")
        normalized = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise TypeError("metadata entry must be an object")
            # Support both new and old field names
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
            # Return tuple format, complying with Solidity struct encoding requirements
            # Field names are (metadataKey, metadataValue) but tuple encoding only needs values
            normalized.append((key, value_bytes))
        return normalized

    def resolve_chain_id(self) -> Optional[int]:
        """
        Resolve Chain ID from RPC node.

        Returns:
            Chain ID, or None if resolution fails
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
        Build order commitment hash.

        Calculates keccak256 hash after canonical JSON serialization of order parameters.

        Args:
            order_params: Order parameters dictionary

        Returns:
            Commitment hash (0x prefixed)

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
        Compute request data hash.

        Args:
            request_payload: Request data (dictionary or JSON string)

        Returns:
            Request hash (0x prefixed)
        """
        if isinstance(request_payload, dict):
            payload_bytes = canonical_json(request_payload)
        else:
            payload_bytes = str(request_payload).encode("utf-8")
        return keccak256_hex(payload_bytes)

    def dump_canonical(self, payload: dict) -> str:
        """
        Canonical JSON serialization.

        Args:
            payload: Dictionary to serialize

        Returns:
            Canonical JSON string (keys sorted, no whitespace)
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
        Build A2A request signature.

        Args:
            action_commitment: Action commitment hash
            timestamp: Timestamp
            caller_address: Caller address
            signer: Custom signer (optional)

        Returns:
            Signature (0x prefixed)
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
        Build market order quote request.

        Args:
            asset: Trading pair (e.g., "TRX/USDT")
            amount: Trading amount
            slippage: Slippage tolerance (default 1%)

        Returns:
            Quote request dictionary
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
        Build new market order request.

        Args:
            asset: Trading pair
            amount: Trading amount
            payment_tx_hash: Payment transaction hash
            slippage: Slippage tolerance

        Returns:
            New order request dictionary
        """
        return {
            "asset": asset,
            "amount": amount,
            "slippage": slippage,
            "paymentTxHash": payment_tx_hash,
        }

    def build_x402_quote_request(self, order_params: dict) -> dict:
        """
        Build X402 quote request.

        Args:
            order_params: Order parameters

        Returns:
            X402 quote request dictionary
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
        Build X402 execution request.

        Args:
            action_commitment: Action commitment hash
            order_params: Order parameters
            payment_tx_hash: Payment transaction hash
            timestamp: Timestamp
            caller_address: Caller address
            include_signature: Whether to include signature

        Returns:
            X402 execution request dictionary
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
        Build payment signature.

        Args:
            action_commitment: Action commitment hash
            payment_address: Payment address
            amount: Payment amount
            timestamp: Timestamp
            signer: Custom signer (optional)

        Returns:
            Payment signature (0x prefixed)
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
        """Normalize to 32 bytes."""
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
        """Normalize to bytes."""
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
        """ABI encode unsigned integer (32 bytes)."""
        return int(value).to_bytes(32, byteorder="big")

    @staticmethod
    def _abi_encode_address(address: str) -> bytes:
        """
        ABI encode address (32 bytes, left-padded with zeros).

        Supports TRON base58 addresses and EVM hex addresses.

        Raises:
            InvalidAddressError: Invalid address format
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
