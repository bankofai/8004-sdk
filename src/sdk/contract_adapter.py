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
        validation_registry_abi_path: Optional[str] = None,
        reputation_registry_abi_path: Optional[str] = None,
        fee_limit: Optional[int] = None,
    ) -> None:
        self.rpc_url = rpc_url
        self.identity_registry = identity_registry
        self.validation_registry = validation_registry
        self.reputation_registry = reputation_registry
        self.identity_registry_abi_path = identity_registry_abi_path
        self.validation_registry_abi_path = validation_registry_abi_path
        self.reputation_registry_abi_path = reputation_registry_abi_path
        self.fee_limit = fee_limit
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from tronpy import Tron
                from tronpy.providers import HTTPProvider
            except ImportError as exc:
                raise RuntimeError("tronpy is required for TronContractAdapter") from exc
            self._client = Tron(provider=HTTPProvider(self.rpc_url))
            if self.fee_limit:
                self._client.conf["fee_limit"] = self.fee_limit
        return self._client

    def _resolve_contract(self, contract: str):
        address = None
        abi_path = None
        if contract == "identity":
            address = self.identity_registry
            abi_path = self.identity_registry_abi_path
        elif contract == "validation":
            address = self.validation_registry
            abi_path = self.validation_registry_abi_path
        elif contract == "reputation":
            address = self.reputation_registry
            abi_path = self.reputation_registry_abi_path
        if not address:
            raise RuntimeError(f"Contract address missing for {contract}")
        client = self._get_client()
        contract_ref = client.get_contract(address)
        if abi_path:
            path = os.path.expanduser(abi_path)
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                abi = data.get("abi", data)
                if contract == "identity" and isinstance(abi, list):
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
                    "loaded %s abi path=%s", contract, path
                )
            except Exception as exc:
                logging.getLogger("trc8004.adapter").warning(
                    "failed to load %s abi path=%s error=%s", contract, path, exc
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
            try:
                client = self._get_client()
                address = signer.get_address()
                resource = client.get_account_resource(address)
                energy_limit = resource.get("EnergyLimit", 0)
                energy_used = resource.get("EnergyUsed", 0)
                energy_left = max(energy_limit - energy_used, 0)
                logging.getLogger("trc8004.adapter").info(
                    "register energy_left=%s energy_limit=%s energy_used=%s",
                    energy_left,
                    energy_limit,
                    energy_used,
                )
            except Exception as exc:
                logging.getLogger("trc8004.adapter").warning(
                    "register energy check failed error=%s",
                    exc,
                )
        function = self._pick_function(contract_ref, method, params)
        if method == "register":
            logging.getLogger("trc8004.adapter").info("register function=%s", function)
        txn = function(*params).with_owner(signer.get_address()).build()
        signed = signer.sign_tx(txn)
        result = signed.broadcast().wait()
        return result.get("id")
