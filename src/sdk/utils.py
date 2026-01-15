"""
TRC-8004 SDK 工具函数模块

提供加密哈希、JSON 序列化等基础工具函数。

Functions:
    canonical_json: 规范化 JSON 序列化（字节）
    canonical_json_str: 规范化 JSON 序列化（字符串）
    sha256_hex: SHA-256 哈希
    hmac_sha256_hex: HMAC-SHA256 签名
    keccak256_hex: Keccak-256 哈希（十六进制）
    keccak256_bytes: Keccak-256 哈希（字节）

Example:
    >>> from sdk.utils import keccak256_hex, canonical_json
    >>> data = {"key": "value", "num": 123}
    >>> hash_hex = keccak256_hex(canonical_json(data))
    >>> print(hash_hex)  # 0x...

Note:
    - 规范化 JSON 使用键排序和紧凑格式，确保相同数据产生相同哈希
    - Keccak-256 是以太坊/TRON 使用的哈希算法，与 SHA3-256 略有不同
"""

import hashlib
import hmac
import json
from typing import Any, Dict

from Crypto.Hash import keccak


def canonical_json(payload: Dict[str, Any]) -> bytes:
    """
    将字典序列化为规范化的 JSON 字节串。

    规范化规则：
    - 键按字母顺序排序
    - 使用紧凑格式（无空格）
    - 使用 UTF-8 编码

    Args:
        payload: 待序列化的字典

    Returns:
        规范化的 JSON 字节串

    Example:
        >>> canonical_json({"b": 2, "a": 1})
        b'{"a":1,"b":2}'

    Note:
        规范化确保相同的数据结构总是产生相同的字节串，
        这对于生成确定性哈希至关重要。
    """
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def canonical_json_str(payload: Dict[str, Any]) -> str:
    """
    将字典序列化为规范化的 JSON 字符串。

    与 canonical_json 相同的规范化规则，但返回字符串而非字节。

    Args:
        payload: 待序列化的字典

    Returns:
        规范化的 JSON 字符串

    Example:
        >>> canonical_json_str({"b": 2, "a": 1})
        '{"a":1,"b":2}'
    """
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def sha256_hex(payload: bytes) -> str:
    """
    计算 SHA-256 哈希值。

    Args:
        payload: 待哈希的字节串

    Returns:
        带 0x 前缀的十六进制哈希字符串（64 字符 + 前缀）

    Example:
        >>> sha256_hex(b"hello")
        '0x2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
    """
    return "0x" + hashlib.sha256(payload).hexdigest()


def hmac_sha256_hex(key: bytes, payload: bytes) -> str:
    """
    计算 HMAC-SHA256 签名。

    Args:
        key: 密钥字节串
        payload: 待签名的消息字节串

    Returns:
        带 0x 前缀的十六进制签名字符串

    Example:
        >>> hmac_sha256_hex(b"secret", b"message")
        '0x...'

    Note:
        HMAC 提供消息认证，确保消息未被篡改且来自持有密钥的发送方。
    """
    return "0x" + hmac.new(key, payload, hashlib.sha256).hexdigest()


def keccak256_hex(payload: bytes) -> str:
    """
    计算 Keccak-256 哈希值（十六进制格式）。

    Keccak-256 是以太坊和 TRON 区块链使用的哈希算法。

    Args:
        payload: 待哈希的字节串

    Returns:
        带 0x 前缀的十六进制哈希字符串（64 字符 + 前缀）

    Example:
        >>> keccak256_hex(b"hello")
        '0x1c8aff950685c2ed4bc3174f3472287b56d9517b9c948127319a09a7a36deac8'

    Note:
        Keccak-256 与 NIST 标准化的 SHA3-256 略有不同，
        以太坊在 SHA3 标准化之前就采用了 Keccak。
    """
    hasher = keccak.new(digest_bits=256)
    hasher.update(payload)
    return "0x" + hasher.hexdigest()


def keccak256_bytes(payload: bytes) -> bytes:
    """
    计算 Keccak-256 哈希值（字节格式）。

    与 keccak256_hex 相同，但返回原始字节而非十六进制字符串。

    Args:
        payload: 待哈希的字节串

    Returns:
        32 字节的哈希值

    Example:
        >>> len(keccak256_bytes(b"hello"))
        32

    Note:
        当需要将哈希用于进一步的密码学操作（如签名）时，
        使用字节格式更高效。
    """
    hasher = keccak.new(digest_bits=256)
    hasher.update(payload)
    return hasher.digest()
