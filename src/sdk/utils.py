import hashlib
import hmac
import json
from typing import Any, Dict

from Crypto.Hash import keccak


def canonical_json(payload: Dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def canonical_json_str(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def sha256_hex(payload: bytes) -> str:
    return "0x" + hashlib.sha256(payload).hexdigest()


def hmac_sha256_hex(key: bytes, payload: bytes) -> str:
    return "0x" + hmac.new(key, payload, hashlib.sha256).hexdigest()


def keccak256_hex(payload: bytes) -> str:
    hasher = keccak.new(digest_bits=256)
    hasher.update(payload)
    return "0x" + hasher.hexdigest()


def keccak256_bytes(payload: bytes) -> bytes:
    hasher = keccak.new(digest_bits=256)
    hasher.update(payload)
    return hasher.digest()
