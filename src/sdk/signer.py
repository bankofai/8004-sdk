import hashlib
from typing import Optional

from .utils import hmac_sha256_hex


class Signer:
    def get_address(self) -> str:
        raise NotImplementedError

    def sign_tx(self, unsigned_tx: bytes) -> bytes:
        raise NotImplementedError

    def sign_message(self, payload: bytes) -> str:
        raise NotImplementedError


class SimpleSigner(Signer):
    """
    MVP signer placeholder.

    This uses HMAC-SHA256 over the payload. It is not a real chain signature,
    but keeps the interface usable for local development.
    """

    def __init__(self, private_key: Optional[str] = None) -> None:
        if private_key is None:
            private_key = "development-key"
        self._private_key = private_key.encode("utf-8")
        self._address = self._derive_address(private_key)

    def get_address(self) -> str:
        return self._address

    def sign_tx(self, unsigned_tx: bytes) -> bytes:
        signature = hmac_sha256_hex(self._private_key, unsigned_tx).encode("utf-8")
        return unsigned_tx + b"|" + signature

    def sign_message(self, payload: bytes) -> str:
        return hmac_sha256_hex(self._private_key, payload)

    @staticmethod
    def _derive_address(private_key: str) -> str:
        digest = hashlib.sha256(private_key.encode("utf-8")).hexdigest()
        return "T" + digest[:33]
