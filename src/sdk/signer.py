import hashlib
from typing import Optional, Any

from .utils import hmac_sha256_hex


class Signer:
    def get_address(self) -> str:
        raise NotImplementedError

    def sign_tx(self, unsigned_tx: Any) -> Any:
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

    def sign_tx(self, unsigned_tx: Any) -> Any:
        if isinstance(unsigned_tx, bytes):
            signature = hmac_sha256_hex(self._private_key, unsigned_tx).encode("utf-8")
            return unsigned_tx + b"|" + signature
        return unsigned_tx

    def sign_message(self, payload: bytes) -> str:
        return hmac_sha256_hex(self._private_key, payload)

    @staticmethod
    def _derive_address(private_key: str) -> str:
        digest = hashlib.sha256(private_key.encode("utf-8")).hexdigest()
        return "T" + digest[:33]


class TronSigner(Signer):
    def __init__(self, private_key: str) -> None:
        try:
            from tronpy.keys import PrivateKey
        except ImportError as exc:
            raise RuntimeError("tronpy is required for TronSigner") from exc
        self._key = PrivateKey(bytes.fromhex(private_key))
        self._address = self._key.public_key.to_base58check_address()

    def get_address(self) -> str:
        return self._address

    def sign_tx(self, unsigned_tx: Any) -> Any:
        return unsigned_tx.sign(self._key)

    def sign_message(self, payload: bytes) -> str:
        signature = self._key.sign_msg_hash(payload)
        return "0x" + signature.hex()
