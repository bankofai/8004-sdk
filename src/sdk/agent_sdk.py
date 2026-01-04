from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .contract_adapter import ContractAdapter, DummyContractAdapter, TronContractAdapter
from .signer import Signer, SimpleSigner, TronSigner
from .utils import canonical_json, keccak256_hex, keccak256_bytes


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
                signer = TronSigner(private_key=private_key.replace("0x", ""))
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
        params = [validator_addr, agent_id, request_uri, request_hash]
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
        params = [request_hash, response, response_uri, response_hash, tag]
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
        params = [agent_id, score, tag1, tag2, fileuri, filehash, feedback_auth]
        return self.contract_adapter.send("reputation", "giveFeedback", params, signer)

    def register_agent(
        self,
        token_uri: str,
        metadata: Optional[bytes] = None,
        signer: Optional[Signer] = None,
    ) -> str:
        signer = signer or self.signer
        params = [token_uri, metadata]
        return self.contract_adapter.send("identity", "register", params, signer)

    def update_metadata(
        self,
        agent_id: int,
        token_uri: str,
        signer: Optional[Signer] = None,
    ) -> str:
        signer = signer or self.signer
        params = [agent_id, token_uri]
        return self.contract_adapter.send("identity", "updateMetadata", params, signer)


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
        payload = {
            "agentId": agent_id,
            "clientAddress": client_addr,
            "indexLimit": index_limit,
            "expiry": expiry,
            "chainId": chain_id,
            "identityRegistry": identity_registry,
            "signerAddress": signer.get_address(),
        }
        message = keccak256_bytes(canonical_json(payload))
        return signer.sign_message(message)

    def build_commitment(self, order_params: dict) -> str:
        payload = canonical_json(order_params)
        return keccak256_hex(payload)

    def compute_request_hash(self, request_payload: str) -> str:
        return keccak256_hex(request_payload.encode("utf-8"))

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
