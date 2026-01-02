import time
from typing import Any, List

from .signer import Signer


class ContractAdapter:
    def call(self, method: str, params: List[Any]) -> Any:
        raise NotImplementedError

    def send(self, method: str, params: List[Any], signer: Signer) -> str:
        raise NotImplementedError


class DummyContractAdapter(ContractAdapter):
    """
    Local stub adapter that returns deterministic tx ids.
    """

    def call(self, method: str, params: List[Any]) -> Any:
        return {"method": method, "params": params}

    def send(self, method: str, params: List[Any], signer: Signer) -> str:
        stamp = int(time.time() * 1000)
        return f"0x{method}-{stamp}"
