from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .contract_adapter import ContractAdapter, DummyContractAdapter, TronContractAdapter
from .signer import Signer, SimpleSigner, TronSigner
from .utils import canonical_json, canonical_json_str, keccak256_hex, keccak256_bytes


def _is_hex_key(value: str) -> bool:
    if not value:
        return False
    try:
        bytes.fromhex(value)
    except ValueError:
        return False
    return True


@dataclass
class SDKConfig:
    rpc_url: str = "https://nile.trongrid.io"
    network: str = "tron:nile"
    timeout: int = 10
    retry: int = 2
    identity_registry: Optional[str] = None
    validation_registry: Optional[str] = None
    reputation_registry: Optional[str] = None


class AgentSDK:
    def __init__(
        self,
        private_key: Optional[str] = None,
        rpc_url: Optional[str] = None,
        network: Optional[str] = None,
        identity_registry: Optional[str] = None,
        validation_registry: Optional[str] = None,
        reputation_registry: Optional[str] = None,
        identity_registry_abi_path: Optional[str] = None,
        signer: Optional[Signer] = None,
        contract_adapter: Optional[ContractAdapter] = None,
    ) -> None:
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

        if signer is None:
            if self.config.network.startswith("tron") and private_key:
                cleaned_key = private_key.replace("0x", "")
                if _is_hex_key(cleaned_key):
                    signer = TronSigner(private_key=cleaned_key)
                else:
                    signer = SimpleSigner(private_key=private_key)
            else:
                signer = SimpleSigner(private_key=private_key)
        self.signer = signer

        if contract_adapter is None:
            if self.config.network.startswith("tron"):
                contract_adapter = TronContractAdapter(
                    rpc_url=self.config.rpc_url,
                    identity_registry=self.config.identity_registry,
                    validation_registry=self.config.validation_registry,
                    reputation_registry=self.config.reputation_registry,
                    identity_registry_abi_path=identity_registry_abi_path,
                )
            else:
                contract_adapter = DummyContractAdapter()
        self.contract_adapter = contract_adapter

    def validation_request(
        self,
        validator_addr: str,
        agent_id: int,
        request_uri: str,
        request_hash: Optional[str] = None,
        signer: Optional[Signer] = None,
    ) -> str:
        signer = signer or self.signer
        params = [validator_addr, agent_id, request_uri, self._normalize_bytes32(request_hash)]
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
        signer = signer or self.signer
        params = [
            self._normalize_bytes32(request_hash),
            response,
            response_uri or "",
            self._normalize_bytes32(response_hash),
            self._normalize_bytes32(tag),
        ]
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
        signer = signer or self.signer
        params = [
            agent_id,
            score,
            self._normalize_bytes32(tag1),
            self._normalize_bytes32(tag2),
            fileuri or "",
            self._normalize_bytes32(filehash),
            self._normalize_bytes(feedback_auth),
        ]
        return self.contract_adapter.send("reputation", "giveFeedback", params, signer)

    def register_agent(
        self,
        token_uri: str,
        metadata: Optional[list[dict]] = None,
        signer: Optional[Signer] = None,
    ) -> str:
        signer = signer or self.signer
        if metadata is not None:
            raise ValueError("register(string) only: metadata not supported")
        params = [token_uri]
        return self.contract_adapter.send("identity", "register", params, signer)

    def update_metadata(
        self,
        agent_id: int,
        key: str,
        value: str | bytes,
        signer: Optional[Signer] = None,
    ) -> str:
        signer = signer or self.signer
        if isinstance(value, str):
            value = value.encode("utf-8")
        params = [agent_id, key, value]
        return self.contract_adapter.send("identity", "setMetadata", params, signer)


    def build_feedback_auth(
        self,
        agent_id: int,
        client_addr: str,
        index_limit: int,
        expiry: int,
        chain_id: int,
        identity_registry: str,
        signer: Optional[Signer] = None,
    ) -> str:
        signer = signer or self.signer
        signer_addr = signer.get_address()
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
        struct_hash = keccak256_bytes(struct_bytes)
        message = keccak256_bytes(b"\x19Ethereum Signed Message:\n32" + struct_hash)
        signature = self._normalize_bytes(signer.sign_message(message))
        return "0x" + (struct_bytes + signature).hex()

    def build_commitment(self, order_params: dict) -> str:
        payload = canonical_json(order_params)
        return keccak256_hex(payload)

    def compute_request_hash(self, request_payload: str | dict) -> str:
        if isinstance(request_payload, dict):
            payload_bytes = canonical_json(request_payload)
        else:
            payload_bytes = str(request_payload).encode("utf-8")
        return keccak256_hex(payload_bytes)

    def dump_canonical(self, payload: dict) -> str:
        return canonical_json_str(payload)

    def build_a2a_signature(
        self,
        action_commitment: str,
        timestamp: int,
        caller_address: str,
        signer: Optional[Signer] = None,
    ) -> str:
        signer = signer or self.signer
        payload = {
            "actionCommitment": action_commitment,
            "timestamp": timestamp,
            "callerAddress": caller_address,
        }
        message = keccak256_bytes(canonical_json(payload))
        return signer.sign_message(message)

    def build_market_order_quote_request(self, asset: str, amount: float, slippage: float = 0.01) -> dict:
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
        return {
            "asset": asset,
            "amount": amount,
            "slippage": slippage,
            "paymentTxHash": payment_tx_hash,
        }

    def build_x402_quote_request(self, order_params: dict) -> dict:
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
        signer = signer or self.signer
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
        if value is None:
            return b"\x00" * 32
        if isinstance(value, bytes):
            return value
        cleaned = value[2:] if value.startswith("0x") else value
        if not cleaned:
            return b"\x00" * 32
        return bytes.fromhex(cleaned)

    @staticmethod
    def _normalize_bytes(value: Optional[str | bytes]) -> bytes:
        if value is None:
            return b""
        if isinstance(value, bytes):
            return value
        cleaned = value[2:] if value.startswith("0x") else value
        return bytes.fromhex(cleaned)

    @staticmethod
    def _abi_encode_uint(value: int) -> bytes:
        return int(value).to_bytes(32, byteorder="big")

    @staticmethod
    def _abi_encode_address(address: str) -> bytes:
        addr = address
        if addr.startswith("T"):
            try:
                from tronpy.keys import to_hex_address
            except Exception as exc:  # pragma: no cover - optional dependency
                raise ValueError("tronpy required to convert base58 address") from exc
            addr = to_hex_address(addr)
        if addr.startswith("0x"):
            addr = addr[2:]
        if len(addr) != 40:
            raise ValueError("address must be 20 bytes")
        return bytes.fromhex(addr).rjust(32, b"\x00")
