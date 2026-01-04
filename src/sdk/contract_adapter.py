import time
from typing import Any, List, Optional

from .signer import Signer


class ContractAdapter:
    def call(self, method: str, params: List[Any]) -> Any:
        raise NotImplementedError

    def send(self, contract: str, method: str, params: List[Any], signer: Signer) -> str:
        raise NotImplementedError


class DummyContractAdapter(ContractAdapter):
    """
    Local stub adapter that returns deterministic tx ids.
    """

    def call(self, method: str, params: List[Any]) -> Any:
        return {"method": method, "params": params}

    def send(self, contract: str, method: str, params: List[Any], signer: Signer) -> str:
        stamp = int(time.time() * 1000)
        return f"0x{contract}-{method}-{stamp}"


class TronContractAdapter(ContractAdapter):
    def __init__(
        self,
        rpc_url: str,
        identity_registry: Optional[str],
        validation_registry: Optional[str],
        reputation_registry: Optional[str],
    ) -> None:
        self.rpc_url = rpc_url
        self.identity_registry = identity_registry
        self.validation_registry = validation_registry
        self.reputation_registry = reputation_registry
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from tronpy import Tron
                from tronpy.providers import HTTPProvider
            except ImportError as exc:
                raise RuntimeError("tronpy is required for TronContractAdapter") from exc
            self._client = Tron(provider=HTTPProvider(self.rpc_url))
        return self._client

    def _resolve_contract(self, contract: str):
        address = None
        if contract == "identity":
            address = self.identity_registry
        elif contract == "validation":
            address = self.validation_registry
        elif contract == "reputation":
            address = self.reputation_registry
        if not address:
            raise RuntimeError(f"Contract address missing for {contract}")
        client = self._get_client()
        return client.get_contract(address)

    def call(self, method: str, params: List[Any]) -> Any:
        raise NotImplementedError("Use send with contract name for TronContractAdapter")

    def send(self, contract: str, method: str, params: List[Any], signer: Signer) -> str:
        contract_ref = self._resolve_contract(contract)
        txn = contract_ref.functions[method](*params).with_owner(signer.get_address()).build()
        signed = signer.sign_tx(txn)
        result = signed.broadcast().wait()
        return result.get("id")
