"""
TRON-8004 SDK Signer Module

Provides abstract interfaces and implementations for blockchain transactions and message signing.

Classes:
    Signer: Abstract base class for signers
    SimpleSigner: Simple signer for development and testing (HMAC-SHA256)
    TronSigner: TRON blockchain signer (secp256k1)

Example:
    >>> from sdk.signer import TronSigner
    >>> signer = TronSigner(private_key="your_hex_private_key")
    >>> address = signer.get_address()
    >>> signature = signer.sign_message(b"hello")

Note:
    - SimpleSigner is for local development and testing only, providing no real cryptographic security
    - TronSigner requires the tronpy library
    - Extending to other chains only requires implementing the Signer interface
"""

import hashlib
from typing import Optional, Any

from .utils import hmac_sha256_hex


class Signer:
    """
    Abstract base class for signers.

    Defines the standard interface for blockchain signers; all concrete implementations must inherit from this class.

    Methods:
        get_address: Get the signer's blockchain address
        sign_tx: Sign a transaction
        sign_message: Sign an arbitrary message

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
        Get the signer's blockchain address.

        Returns:
            Blockchain address string (format depends on the specific chain)

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError

    def sign_tx(self, unsigned_tx: Any) -> Any:
        """
        Sign an unsigned transaction.

        Args:
            unsigned_tx: Unsigned transaction object (format depends on the specific chain)

        Returns:
            Signed transaction object

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError

    def sign_message(self, payload: bytes) -> str:
        """
        Sign an arbitrary message.

        Used for EIP-191 style message signing, commonly used for off-chain verification.

        Args:
            payload: Message bytes to sign (usually a hash)

        Returns:
            Signed hexadecimal string (with 0x prefix)

        Raises:
            NotImplementedError: Subclasses must implement this method
        """
        raise NotImplementedError


class SimpleSigner(Signer):
    """
    Simple signer for development and testing.

    Uses HMAC-SHA256 for signing, not a real blockchain signature,
    but maintains interface consistency to facilitate local development and unit testing.

    Attributes:
        _private_key: Private key bytes
        _address: Derived pseudo-address

    Args:
        private_key: Private key string, defaults to "development-key"

    Example:
        >>> signer = SimpleSigner(private_key="my-test-key")
        >>> signer.get_address()
        'T...'
        >>> signer.sign_message(b"hello")
        '0x...'

    Warning:
        This signer is for development and testing only and provides no cryptographic security!
        Use TronSigner or other real blockchain signers for production environments.
    """

    def __init__(self, private_key: Optional[str] = None) -> None:
        """
        Initialize the simple signer.

        Args:
            private_key: Private key string used to derive address and sign.
                        If None, uses the default development key.
        """
        if private_key is None:
            private_key = "development-key"
        self._private_key = private_key.encode("utf-8")
        self._address = self._derive_address(private_key)
    
    @property
    def address(self) -> str:
        """Public address property"""
        return self._address

    def get_address(self) -> str:
        """
        Get the derived pseudo-address.

        Returns:
            34-character pseudo-address starting with 'T'
        """
        return self._address

    def sign_tx(self, unsigned_tx: Any) -> Any:
        """
        Sign a transaction (simplified implementation).

        For byte type transactions, append HMAC signature;
        For other types, return as is.

        Args:
            unsigned_tx: Unsigned transaction

        Returns:
            Signed transaction (bytes) or original transaction
        """
        if isinstance(unsigned_tx, bytes):
            signature = hmac_sha256_hex(self._private_key, unsigned_tx).encode("utf-8")
            return unsigned_tx + b"|" + signature
        return unsigned_tx

    def sign_message(self, payload: bytes) -> str:
        """
        Sign a message using HMAC-SHA256.

        Args:
            payload: Message bytes to sign

        Returns:
            Hexadecimal signature with 0x prefix
        """
        return hmac_sha256_hex(self._private_key, payload)

    @staticmethod
    def _derive_address(private_key: str) -> str:
        """
        Derive a pseudo-address from the private key.

        Uses SHA-256 to hash the private key and takes the first 33 characters as the address.

        Args:
            private_key: Private key string

        Returns:
            Pseudo-address starting with 'T'
        """
        digest = hashlib.sha256(private_key.encode("utf-8")).hexdigest()
        return "T" + digest[:33]


class TronSigner(Signer):
    """
    TRON Blockchain Signer.

    Uses secp256k1 elliptic curve for real blockchain signing,
    compatible with TRON network transactions and message signing.

    Attributes:
        _key: tronpy PrivateKey object
        _address: TRON base58check format address
        address: Public address property (same as _address)

    Args:
        private_key: Hexadecimal format private key (64 characters, without 0x prefix)

    Raises:
        RuntimeError: tronpy library not installed

    Example:
        >>> signer = TronSigner(private_key="abc123...")
        >>> signer.get_address()
        'TJRabPrwbZy45sbavfcjinPJC18kjpRTv8'
        >>> signer.address  # Can also be accessed directly
        'TJRabPrwbZy45sbavfcjinPJC18kjpRTv8'
        >>> signer.sign_message(keccak256_bytes(b"hello"))
        '0x...'

    Note:
        Requires tronpy installation: pip install tronpy
    """

    def __init__(self, private_key: str) -> None:
        """
        Initialize the TRON signer.

        Args:
            private_key: Hexadecimal format private key (64 characters)

        Raises:
            RuntimeError: tronpy library not installed
            ValueError: Invalid private key format
        """
        try:
            from tronpy.keys import PrivateKey
        except ImportError as exc:
            raise RuntimeError("tronpy is required for TronSigner") from exc
        self._key = PrivateKey(bytes.fromhex(private_key))
        self._address = self._key.public_key.to_base58check_address()
    
    @property
    def address(self) -> str:
        """Public address property"""
        return self._address

    def get_address(self) -> str:
        """
        Get TRON address.

        Returns:
            TRON base58check format address (starts with 'T')
        """
        return self._address

    def sign_tx(self, unsigned_tx: Any) -> Any:
        """
        Sign a TRON transaction.

        Args:
            unsigned_tx: tronpy unsigned transaction object

        Returns:
            Signed transaction object
        """
        return unsigned_tx.sign(self._key)

    def sign_message(self, payload: bytes) -> str:
        """
        Sign a message hash.

        Uses secp256k1 ECDSA signature, returns 65-byte signature
        (r: 32 bytes, s: 32 bytes, v: 1 byte).

        Args:
            payload: Message hash (32 bytes)

        Returns:
            Hexadecimal signature with 0x prefix (130 characters + prefix)
        """
        signature = self._key.sign_msg_hash(payload)
        return "0x" + signature.hex()
