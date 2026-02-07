"""
TRON-8004 SDK Utility Module

Provides foundational utility functions like encryption, hashing, JSON serialization, etc.

Functions:
    canonical_json: Canonical JSON serialization (bytes)
    canonical_json_str: Canonical JSON serialization (string)
    sha256_hex: SHA-256 hash
    hmac_sha256_hex: HMAC-SHA256 signature
    keccak256_hex: Keccak-256 hash (hexadecimal)
    keccak256_bytes: Keccak-256 hash (bytes)

Example:
    >>> from sdk.utils import keccak256_hex, canonical_json
    >>> data = {"key": "value", "num": 123}
    >>> hash_hex = keccak256_hex(canonical_json(data))
    >>> print(hash_hex)  # 0x...

Note:
    - Canonical JSON uses key sorting and compact format to ensure identical data produces identical hashes
    - Keccak-256 is the hash algorithm used by Ethereum/TRON, slightly different from SHA3-256
"""

import hashlib
import hmac
import json
from typing import Any, Dict

from Crypto.Hash import keccak


def canonical_json(payload: Dict[str, Any]) -> bytes:
    """
    Serialize dictionary to canonical JSON bytes.

    Canonicalization rules:
    - Sort keys alphabetically
    - Use compact format (no whitespace)
    - Use UTF-8 encoding

    Args:
        payload: Dictionary to serialize

    Returns:
        Canonical JSON bytes

    Example:
        >>> canonical_json({"b": 2, "a": 1})
        b'{"a":1,"b":2}'

    Note:
        Canonicalization ensures the same data structure always produces the same byte string,
        which is critical for generating deterministic hashes.
    """
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def canonical_json_str(payload: Dict[str, Any]) -> str:
    """
    Serialize dictionary to canonical JSON string.

    Same canonicalization rules as canonical_json, but returns string instead of bytes.

    Args:
        payload: Dictionary to serialize

    Returns:
        Canonical JSON string

    Example:
        >>> canonical_json_str({"b": 2, "a": 1})
        '{"a":1,"b":2}'
    """
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def sha256_hex(payload: bytes) -> str:
    """
    Calculate SHA-256 hash value.

    Args:
        payload: Bytes to hash

    Returns:
        Hexadecimal hash string with 0x prefix (64 chars + prefix)

    Example:
        >>> sha256_hex(b"hello")
        '0x2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
    """
    return "0x" + hashlib.sha256(payload).hexdigest()


def hmac_sha256_hex(key: bytes, payload: bytes) -> str:
    """
    Calculate HMAC-SHA256 signature.

    Args:
        key: Key bytes
        payload: Message bytes to sign

    Returns:
        Hexadecimal signature string with 0x prefix

    Example:
        >>> hmac_sha256_hex(b"secret", b"message")
        '0x...'

    Note:
        HMAC provides message authentication, ensuring the message has not been tampered with and comes from the sender holding the key.
    """
    return "0x" + hmac.new(key, payload, hashlib.sha256).hexdigest()


def keccak256_hex(payload: bytes) -> str:
    """
    Calculate Keccak-256 hash value (hexadecimal format).

    Keccak-256 is the hash algorithm used by Ethereum and TRON blockchains.

    Args:
        payload: Bytes to hash

    Returns:
        Hexadecimal hash string with 0x prefix (64 chars + prefix)

    Example:
        >>> keccak256_hex(b"hello")
        '0x1c8aff950685c2ed4bc3174f3472287b56d9517b9c948127319a09a7a36deac8'

    Note:
        Keccak-256 is slightly different from the NIST standardized SHA3-256,
        Ethereum adopted Keccak before SHA3 standardization.
    """
    hasher = keccak.new(digest_bits=256)
    hasher.update(payload)
    return "0x" + hasher.hexdigest()


def keccak256_bytes(payload: bytes) -> bytes:
    """
    Calculate Keccak-256 hash value (bytes format).

    Same as keccak256_hex, but returns raw bytes instead of hexadecimal string.

    Args:
        payload: Bytes to hash

    Returns:
        32-byte hash value

    Example:
        >>> len(keccak256_bytes(b"hello"))
        32

    Note:
        It is more efficient to use bytes format when the hash needs to be used for further cryptographic operations (e.g., signing).
    """
    hasher = keccak.new(digest_bits=256)
    hasher.update(payload)
    return hasher.digest()
