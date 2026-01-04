import hashlib
import hmac
import json
from typing import Any, Dict


def canonical_json(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sha256_hex(payload: bytes) -> str:
    return "0x" + hashlib.sha256(payload).hexdigest()


def hmac_sha256_hex(key: bytes, payload: bytes) -> str:
    return "0x" + hmac.new(key, payload, hashlib.sha256).hexdigest()


def keccak256_hex(payload: bytes) -> str:
    return "0x" + hashlib.sha3_256(payload).hexdigest()


def keccak256_bytes(payload: bytes) -> bytes:
    return hashlib.sha3_256(payload).digest()
