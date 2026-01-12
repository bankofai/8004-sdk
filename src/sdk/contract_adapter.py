import json
import logging
import os
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
        identity_registry_abi_path: Optional[str] = None,
    ) -> None:
        self.rpc_url = rpc_url
        self.identity_registry = identity_registry
        self.validation_registry = validation_registry
        self.reputation_registry = reputation_registry
        self.identity_registry_abi_path = identity_registry_abi_path
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
        contract_ref = client.get_contract(address)
        if contract == "identity" and self.identity_registry_abi_path:
            path = os.path.expanduser(self.identity_registry_abi_path)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                abi = data.get("abi", data)
                if isinstance(abi, list):
                    register_overloads = [
                        item
                        for item in abi
                        if item.get("type") == "function" and item.get("name") == "register"
                    ]
                    preferred = [
                        item
                        for item in register_overloads
                        if len(item.get("inputs", [])) == 1
                    ]
                    if preferred:
                        abi = [
                            item
                            for item in abi
                            if not (item.get("type") == "function" and item.get("name") == "register")
                        ]
                        abi = preferred + abi
                contract_ref.abi = abi
                contract_ref._functions = None
                contract_ref._events = None
                logging.getLogger("trc8004.adapter").info(
                    "loaded identity abi path=%s", path
                )
            except Exception as exc:
                logging.getLogger("trc8004.adapter").warning(
                    "failed to load identity abi path=%s error=%s", path, exc
                )
        return contract_ref

    @staticmethod
    def _pick_function(contract_ref, method: str, params: List[Any]):
        def _get(name: str):
            return getattr(contract_ref.functions, name)

        if method == "register" and "(" not in method:
            overloads = []
            if len(params) == 1:
                overloads = ["register(string)"]
            elif len(params) == 2:
                overloads = ["register(string,(string,bytes)[])"]
            for name in overloads:
                try:
                    print(f"[adapter] register params={params} try_function={name}")
                    return _get(name)
                except Exception:
                    pass
            try:
                print(f"[adapter] register params={params} try_function={method}")
                return _get(method)
            except Exception:
                pass
            raise KeyError("register overload not found")
        try:
            return _get(method)
        except Exception:
            pass
        raise KeyError(f"Contract function not found: {method}")

    def call(self, method: str, params: List[Any]) -> Any:
        raise NotImplementedError("Use send with contract name for TronContractAdapter")

    def send(self, contract: str, method: str, params: List[Any], signer: Signer) -> str:
        contract_ref = self._resolve_contract(contract)
        if method == "register":
            logging.getLogger("trc8004.adapter").info(
                "register token_uri=%s",
                params[0] if params else None,
            )
        function = self._pick_function(contract_ref, method, params)
        if method == "register":
            logging.getLogger("trc8004.adapter").info("register function=%s", function)
        txn = function(*params).with_owner(signer.get_address()).build()
        signed = signer.sign_tx(txn)
        result = signed.broadcast().wait()
        return result.get("id")
