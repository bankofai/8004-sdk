"""
TRON-8004 Contract Adapter

Provides an abstraction layer for interacting with different blockchains, supporting:
- DummyContractAdapter: Local development/testing
- TronContractAdapter: TRON Blockchain
- (Future) EVMContractAdapter: EVM-compatible chains
"""

import logging
import time
from typing import Any, List, Optional

from .exceptions import (
    ContractCallError,
    ContractFunctionNotFoundError,
    InsufficientEnergyError,
    MissingContractAddressError,
    NetworkError,
    TransactionFailedError,
)
from .retry import RetryConfig, DEFAULT_RETRY_CONFIG, retry
from .signer import Signer

logger = logging.getLogger("tron8004.adapter")


class ContractAdapter:
    """
    Contract Adapter Abstract Base Class.

    Defines unified interfaces for contract interaction.
    """

    def call(self, contract: str, method: str, params: List[Any]) -> Any:
        """
        Call contract read-only method.

        Args:
            contract: Contract name ("identity", "validation", "reputation")
            method: Method name
            params: Parameter list

        Returns:
            Call result
        """
        raise NotImplementedError

    def send(self, contract: str, method: str, params: List[Any], signer: Signer) -> str:
        """
        Send contract transaction.

        Args:
            contract: Contract name
            method: Method name
            params: Parameter list
            signer: Signer

        Returns:
            Transaction ID
        """
        raise NotImplementedError


class DummyContractAdapter(ContractAdapter):
    """
    Adapter for local testing.

    Returns deterministic transaction IDs without actual blockchain interaction.
    Suitable for unit testing and local development.
    """

    def call(self, contract: str, method: str, params: List[Any]) -> Any:
        return {"contract": contract, "method": method, "params": params}

    def send(self, contract: str, method: str, params: List[Any], signer: Signer) -> str:
        stamp = int(time.time() * 1000)
        return f"0x{contract}-{method}-{stamp}"


class TronContractAdapter(ContractAdapter):
    """
    TRON Blockchain Contract Adapter.

    Interacts with TRON blockchain using tronpy library.

    Args:
        rpc_url: TRON RPC node URL
        identity_registry: IdentityRegistry contract address
        validation_registry: ValidationRegistry contract address
        reputation_registry: ReputationRegistry contract address
        fee_limit: Transaction fee limit in sun
        retry_config: Retry configuration

    Example:
        >>> adapter = TronContractAdapter(
        ...     rpc_url="https://nile.trongrid.io",
        ...     identity_registry="TIdentity...",
        ...     fee_limit=10_000_000,
        ... )
    """

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
        retry_config: Optional[RetryConfig] = None,
    ) -> None:
        self.rpc_url = rpc_url
        self.identity_registry = identity_registry
        self.validation_registry = validation_registry
        self.reputation_registry = reputation_registry
        self.identity_registry_abi_path = identity_registry_abi_path
        self.validation_registry_abi_path = validation_registry_abi_path
        self.reputation_registry_abi_path = reputation_registry_abi_path
        self.fee_limit = fee_limit or 10_000_000
        self.retry_config = retry_config or DEFAULT_RETRY_CONFIG
        self._client = None

    def _get_client(self):
        """Get or create TRON client."""
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
        """Resolve contract address and get contract reference."""
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
            raise MissingContractAddressError(contract)

        client = self._get_client()
        try:
            contract_ref = client.get_contract(address)
            
            # If ABI file path is provided, use ABI from file (supports ABIEncoderV2)
            if abi_path:
                import json
                with open(abi_path) as f:
                    abi_data = json.load(f)
                    if isinstance(abi_data, dict) and "abi" in abi_data:
                        contract_ref.abi = abi_data["abi"]
                    elif isinstance(abi_data, list):
                        contract_ref.abi = abi_data
                logger.debug("Loaded ABI from %s for %s", abi_path, contract)
            else:
                # No ABI file provided, try to fix ABIEncoderV2 tuple types
                # tronpy does not support components field, need to manually expand
                fixed_abi = self._fix_abi_encoder_v2(contract_ref.abi)
                if fixed_abi:
                    contract_ref.abi = fixed_abi
                    logger.debug("Fixed ABIEncoderV2 for %s", contract)
        except Exception as e:
            raise ContractCallError(contract, "get_contract", str(e)) from e

        return contract_ref

    def _fix_abi_encoder_v2(self, abi: list) -> list:
        """
        Fix tuple types for ABIEncoderV2.
        
        tronpy does not support components field, need to expand tuple to basic types.
        Note: On-chain type might be "Function" instead of "function".
        """
        if not abi:
            return abi
        
        def expand_type(item: dict) -> str:
            """Expand tuple type to (type1,type2,...) format."""
            t = item.get("type", "")
            if t == "tuple" or t.startswith("tuple["):
                components = item.get("components", [])
                if not components:
                    # Keep original tuple type when components are missing to avoid "()"
                    return t
                inner = ",".join(expand_type(c) for c in components)
                if t == "tuple":
                    return f"({inner})"
                else:
                    # tuple[] -> (...)[]
                    suffix = t[5:]  # Get [] part
                    return f"({inner}){suffix}"
            return t
        
        fixed = []
        for entry in abi:
            # Use .lower() for case-insensitive comparison
            if entry.get("type", "").lower() != "function":
                fixed.append(entry)
                continue
            
            new_entry = dict(entry)
            
            # Fix inputs
            if "inputs" in entry:
                new_inputs = []
                for inp in entry["inputs"]:
                    new_inp = dict(inp)
                    new_inp["type"] = expand_type(inp)
                    # Remove components field, not needed by tronpy
                    new_inp.pop("components", None)
                    new_inputs.append(new_inp)
                new_entry["inputs"] = new_inputs
            
            # Fix outputs
            if "outputs" in entry:
                new_outputs = []
                for out in entry["outputs"]:
                    new_out = dict(out)
                    new_out["type"] = expand_type(out)
                    new_out.pop("components", None)
                    new_outputs.append(new_out)
                new_entry["outputs"] = new_outputs
            
            fixed.append(new_entry)
        
        return fixed

    @staticmethod
    def _pick_function(contract_ref, method: str, params: List[Any]):
        """Pick contract function (handle overloading)."""

        def _get_overload(name: str, arity: int):
            try:
                from tronpy.contract import ContractMethod
            except ImportError as exc:
                raise RuntimeError("tronpy is required") from exc
            for item in contract_ref.abi:
                if item.get("type", "").lower() != "function":
                    continue
                if item.get("name") != name:
                    continue
                inputs = item.get("inputs", [])
                if len(inputs) == arity:
                    return ContractMethod(item, contract_ref)
            raise ContractFunctionNotFoundError(
                contract_ref.contract_address, name, arity
            )

        def _get(name: str):
            return getattr(contract_ref.functions, name)

        # Handle overloading for register method
        if method == "register" and "(" not in method:
            if len(params) == 0:
                try:
                    return _get_overload("register", 0)
                except Exception:
                    pass
            elif len(params) == 1:
                try:
                    return _get_overload("register", 1)
                except Exception:
                    pass
            elif len(params) == 2:
                try:
                    return _get_overload("register", 2)
                except Exception:
                    pass
            try:
                logger.debug("register params=%s try_function=%s", params, method)
                return _get(method)
            except Exception:
                pass
            raise ContractFunctionNotFoundError(
                contract_ref.contract_address, "register"
            )

        try:
            return _get(method)
        except Exception:
            pass
        raise ContractFunctionNotFoundError(contract_ref.contract_address, method)

    def call(self, contract: str, method: str, params: List[Any]) -> Any:
        """Call contract read-only method."""
        contract_ref = self._resolve_contract(contract)
        function = self._pick_function(contract_ref, method, params)
        try:
            result = function(*params)
            # tronpy's ContractMethod returns result directly in some cases
            # instead of returning an object needing .call()
            if hasattr(result, 'call'):
                return result.call()
            return result
        except Exception as e:
            raise ContractCallError(contract, method, str(e)) from e

    def send(self, contract: str, method: str, params: List[Any], signer: Signer) -> str:
        """
        Send contract transaction (with retry).

        Args:
            contract: Contract name
            method: Method name
            params: Parameter list
            signer: Signer

        Returns:
            Transaction ID

        Raises:
            ContractCallError: Contract call failed
            TransactionFailedError: Transaction execution failed
            InsufficientEnergyError: Insufficient energy
        """
        return self._send_with_retry(contract, method, params, signer)

    @retry(operation_name="contract_send")
    def _send_with_retry(
        self, contract: str, method: str, params: List[Any], signer: Signer
    ) -> str:
        """Send transaction with retry."""
        contract_ref = self._resolve_contract(contract)

        # Check energy (only for register method)
        if method == "register":
            self._check_energy(signer)

        function = self._pick_function(contract_ref, method, params)
        logger.debug(
            "Sending tx: contract=%s, method=%s, params_count=%d",
            contract,
            method,
            len(params),
        )

        try:
            # Try to build transaction using standard way
            try:
                txn = function(*params).with_owner(signer.get_address()).build()
            except ValueError as ve:
                if "ABIEncoderV2" in str(ve):
                    # ABIEncoderV2 requires manual parameter encoding
                    txn = self._build_tx_with_abi_encoder_v2(
                        contract_ref, method, params, signer
                    )
                else:
                    raise
            
            signed = signer.sign_tx(txn)
            result = signed.broadcast().wait()

            tx_id = result.get("id")
            if not tx_id:
                raise TransactionFailedError(reason="No transaction ID in result")

            logger.info("Transaction sent: %s", tx_id)
            return tx_id

        except Exception as e:
            error_msg = str(e).lower()
            if "energy" in error_msg or "bandwidth" in error_msg:
                raise InsufficientEnergyError() from e
            if "revert" in error_msg:
                raise TransactionFailedError(reason=str(e)) from e
            # Network errors are retryable
            if any(
                kw in error_msg
                for kw in ["timeout", "connection", "network", "unavailable"]
            ):
                raise NetworkError(str(e)) from e
            raise ContractCallError(contract, method, str(e)) from e

    def _build_tx_with_abi_encoder_v2(
        self, contract_ref, method: str, params: List[Any], signer: Signer
    ):
        """
        Manually encode ABIEncoderV2 parameters using eth_abi.
        
        tronpy does not support ABIEncoderV2 tuple types, need to manually encode params and build transaction.
        """
        try:
            from eth_abi import encode
            from eth_utils import keccak
        except ImportError:
            raise RuntimeError("eth_abi and eth_utils are required for ABIEncoderV2 encoding")
        
        # Find method ABI (supports overloaded methods)
        # Note: On-chain type might be "Function" instead of "function"
        method_abi = None
        for item in contract_ref.abi:
            if item.get("type", "").lower() == "function" and item.get("name") == method:
                inputs = item.get("inputs", [])
                if len(inputs) == len(params):
                    method_abi = item
                    break
        
        if not method_abi:
            # Print debug info
            logger.debug(
                "Looking for method %s with %d params in ABI with %d entries",
                method, len(params), len(contract_ref.abi)
            )
            for item in contract_ref.abi:
                if item.get("type", "").lower() == "function":
                    logger.debug(
                        "  Found function: %s with %d inputs",
                        item.get("name"), len(item.get("inputs", []))
                    )
            raise ContractFunctionNotFoundError(
                contract_ref.contract_address, method, len(params)
            )
        
        # Build type signature
        def get_type_str(inp: dict) -> str:
            t = inp.get("type", "")
            if t == "tuple" or t.startswith("tuple"):
                components = inp.get("components", [])
                inner = ",".join(get_type_str(c) for c in components)
                if t == "tuple":
                    return f"({inner})"
                else:
                    suffix = t[5:]
                    return f"({inner}){suffix}"
            return t
        
        types = [get_type_str(inp) for inp in method_abi.get("inputs", [])]
        logger.debug("ABIEncoderV2 types: %s", types)
        
        # Encode parameters
        encoded_params = encode(types, params)
        
        # Calculate function selector (keccak256 of function signature)
        sig = f"{method}({','.join(types)})"
        selector = keccak(text=sig)[:4]
        logger.debug("Function signature: %s, selector: %s", sig, selector.hex())
        
        # Build full calldata
        data = selector + encoded_params
        
        # Use tronpy low-level API to build transaction
        client = self._get_client()
        owner_address = signer.get_address()
        
        # Build TriggerSmartContract transaction
        txn = client.trx._build_transaction(
            "TriggerSmartContract",
            {
                "owner_address": owner_address,
                "contract_address": contract_ref.contract_address,
                "data": data.hex(),
            },
            method=method,
        )
        
        return txn

    def _check_energy(self, signer: Signer) -> None:
        """Check account energy."""
        try:
            client = self._get_client()
            address = signer.get_address()
            resource = client.get_account_resource(address)
            energy_limit = resource.get("EnergyLimit", 0)
            energy_used = resource.get("EnergyUsed", 0)
            energy_left = max(energy_limit - energy_used, 0)
            logger.debug(
                "Energy check: left=%d, limit=%d, used=%d",
                energy_left,
                energy_limit,
                energy_used,
            )
            if energy_left < 100_000:
                logger.warning("Low energy: %d", energy_left)
        except Exception as e:
            logger.warning("Energy check failed: %s", e)
