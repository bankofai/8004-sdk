from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .contract_adapter import ContractAdapter, DummyContractAdapter
from .signer import Signer, SimpleSigner
from .utils import canonical_json, sha256_hex


@dataclass
class SDKConfig:
    rpc_url: str = "https://nile.trongrid.io"
    network: str = "nile"
    contract_address: str = "TF..."
    timeout: int = 10
    retry: int = 2


class AgentSDK:
    def __init__(
        self,
        private_key: Optional[str] = None,
        rpc_url: Optional[str] = None,
        network: Optional[str] = None,
        contract_address: Optional[str] = None,
        signer: Optional[Signer] = None,
        contract_adapter: Optional[ContractAdapter] = None,
    ) -> None:
        self.config = SDKConfig()
        if rpc_url is not None:
            self.config.rpc_url = rpc_url
        if network is not None:
            self.config.network = network
        if contract_address is not None:
            self.config.contract_address = contract_address

        if signer is None:
            signer = SimpleSigner(private_key=private_key)
        self.signer = signer

        if contract_adapter is None:
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
        return self.contract_adapter.send("validationRequest", params, signer)

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
        return self.contract_adapter.send("validationResponse", params, signer)

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
        return self.contract_adapter.send("giveFeedback", params, signer)

    def register_agent(
        self,
        token_uri: str,
        metadata: Optional[bytes] = None,
        signer: Optional[Signer] = None,
    ) -> str:
        signer = signer or self.signer
        params = [token_uri, metadata]
        return self.contract_adapter.send("register", params, signer)

    def update_metadata(
        self,
        agent_id: int,
        token_uri: str,
        signer: Optional[Signer] = None,
    ) -> str:
        signer = signer or self.signer
        params = [agent_id, token_uri]
        return self.contract_adapter.send("updateMetadata", params, signer)

    def transfer(
        self,
        to_addr: str,
        amount: int,
        token: Optional[str] = None,
        signer: Optional[Signer] = None,
    ) -> str:
        signer = signer or self.signer
        params = [to_addr, amount, token]
        return self.contract_adapter.send("transfer", params, signer)

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
        message = sha256_hex(canonical_json(payload)).encode("utf-8")
        return signer.sign_message(message)

    def build_commitment(self, order_params: dict) -> str:
        payload = canonical_json(order_params)
        return sha256_hex(payload)

    def compute_request_hash(self, request_payload: str) -> str:
        return sha256_hex(request_payload)

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
        message = sha256_hex(canonical_json(payload)).encode("utf-8")
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
