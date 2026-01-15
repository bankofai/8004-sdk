"""
TRC-8004 SDK 签名器模块

提供区块链交易和消息签名的抽象接口及实现。

Classes:
    Signer: 签名器抽象基类
    SimpleSigner: 开发测试用的简单签名器（HMAC-SHA256）
    TronSigner: TRON 区块链签名器（secp256k1）

Example:
    >>> from sdk.signer import TronSigner
    >>> signer = TronSigner(private_key="your_hex_private_key")
    >>> address = signer.get_address()
    >>> signature = signer.sign_message(b"hello")

Note:
    - SimpleSigner 仅用于本地开发和测试，不提供真正的密码学安全性
    - TronSigner 需要安装 tronpy 库
    - 扩展其他链只需实现 Signer 接口
"""

import hashlib
from typing import Optional, Any

from .utils import hmac_sha256_hex


class Signer:
    """
    签名器抽象基类。

    定义了区块链签名器的标准接口，所有具体实现必须继承此类。

    Methods:
        get_address: 获取签名者的区块链地址
        sign_tx: 签名交易
        sign_message: 签名任意消息

    Example:
        >>> class MySigner(Signer):
        ...     def get_address(self) -> str:
        ...         return "0x..."
        ...     def sign_tx(self, unsigned_tx: Any) -> Any:
        ...         return signed_tx
        ...     def sign_message(self, payload: bytes) -> str:
        ...         return "0x..."
    """

    def get_address(self) -> str:
        """
        获取签名者的区块链地址。

        Returns:
            区块链地址字符串（格式取决于具体链）

        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError

    def sign_tx(self, unsigned_tx: Any) -> Any:
        """
        签名未签名的交易。

        Args:
            unsigned_tx: 未签名的交易对象（格式取决于具体链）

        Returns:
            已签名的交易对象

        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError

    def sign_message(self, payload: bytes) -> str:
        """
        签名任意消息。

        用于 EIP-191 风格的消息签名，常用于链下验证。

        Args:
            payload: 待签名的消息字节串（通常是哈希值）

        Returns:
            签名的十六进制字符串（带 0x 前缀）

        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        raise NotImplementedError


class SimpleSigner(Signer):
    """
    开发测试用的简单签名器。

    使用 HMAC-SHA256 进行签名，不是真正的区块链签名，
    但保持了接口一致性，便于本地开发和单元测试。

    Attributes:
        _private_key: 私钥字节串
        _address: 派生的伪地址

    Args:
        private_key: 私钥字符串，默认为 "development-key"

    Example:
        >>> signer = SimpleSigner(private_key="my-test-key")
        >>> signer.get_address()
        'T...'
        >>> signer.sign_message(b"hello")
        '0x...'

    Warning:
        此签名器仅用于开发测试，不提供密码学安全性！
        生产环境请使用 TronSigner 或其他真正的区块链签名器。
    """

    def __init__(self, private_key: Optional[str] = None) -> None:
        """
        初始化简单签名器。

        Args:
            private_key: 私钥字符串，用于派生地址和签名。
                        如果为 None，使用默认的开发密钥。
        """
        if private_key is None:
            private_key = "development-key"
        self._private_key = private_key.encode("utf-8")
        self._address = self._derive_address(private_key)

    def get_address(self) -> str:
        """
        获取派生的伪地址。

        Returns:
            以 'T' 开头的 34 字符伪地址
        """
        return self._address

    def sign_tx(self, unsigned_tx: Any) -> Any:
        """
        签名交易（简化实现）。

        对于字节类型的交易，追加 HMAC 签名；
        对于其他类型，原样返回。

        Args:
            unsigned_tx: 未签名的交易

        Returns:
            带签名的交易（字节类型）或原交易
        """
        if isinstance(unsigned_tx, bytes):
            signature = hmac_sha256_hex(self._private_key, unsigned_tx).encode("utf-8")
            return unsigned_tx + b"|" + signature
        return unsigned_tx

    def sign_message(self, payload: bytes) -> str:
        """
        使用 HMAC-SHA256 签名消息。

        Args:
            payload: 待签名的消息字节串

        Returns:
            带 0x 前缀的十六进制签名
        """
        return hmac_sha256_hex(self._private_key, payload)

    @staticmethod
    def _derive_address(private_key: str) -> str:
        """
        从私钥派生伪地址。

        使用 SHA-256 哈希私钥，取前 33 个字符作为地址。

        Args:
            private_key: 私钥字符串

        Returns:
            以 'T' 开头的伪地址
        """
        digest = hashlib.sha256(private_key.encode("utf-8")).hexdigest()
        return "T" + digest[:33]


class TronSigner(Signer):
    """
    TRON 区块链签名器。

    使用 secp256k1 椭圆曲线进行真正的区块链签名，
    兼容 TRON 网络的交易和消息签名。

    Attributes:
        _key: tronpy PrivateKey 对象
        _address: TRON base58check 格式地址

    Args:
        private_key: 十六进制格式的私钥（64 字符，不带 0x 前缀）

    Raises:
        RuntimeError: 未安装 tronpy 库

    Example:
        >>> signer = TronSigner(private_key="abc123...")
        >>> signer.get_address()
        'TJRabPrwbZy45sbavfcjinPJC18kjpRTv8'
        >>> signer.sign_message(keccak256_bytes(b"hello"))
        '0x...'

    Note:
        需要安装 tronpy: pip install tronpy
    """

    def __init__(self, private_key: str) -> None:
        """
        初始化 TRON 签名器。

        Args:
            private_key: 十六进制格式的私钥（64 字符）

        Raises:
            RuntimeError: 未安装 tronpy 库
            ValueError: 私钥格式无效
        """
        try:
            from tronpy.keys import PrivateKey
        except ImportError as exc:
            raise RuntimeError("tronpy is required for TronSigner") from exc
        self._key = PrivateKey(bytes.fromhex(private_key))
        self._address = self._key.public_key.to_base58check_address()

    def get_address(self) -> str:
        """
        获取 TRON 地址。

        Returns:
            TRON base58check 格式地址（以 'T' 开头）
        """
        return self._address

    def sign_tx(self, unsigned_tx: Any) -> Any:
        """
        签名 TRON 交易。

        Args:
            unsigned_tx: tronpy 的未签名交易对象

        Returns:
            已签名的交易对象
        """
        return unsigned_tx.sign(self._key)

    def sign_message(self, payload: bytes) -> str:
        """
        签名消息哈希。

        使用 secp256k1 ECDSA 签名，返回 65 字节的签名
        （r: 32 bytes, s: 32 bytes, v: 1 byte）。

        Args:
            payload: 消息哈希（32 字节）

        Returns:
            带 0x 前缀的十六进制签名（130 字符 + 前缀）
        """
        signature = self._key.sign_msg_hash(payload)
        return "0x" + signature.hex()
