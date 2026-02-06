"""
TRC-8004 合约适配器

提供与不同区块链交互的抽象层，支持：
- DummyContractAdapter: 本地开发/测试
- TronContractAdapter: TRON 区块链
- (未来) EVMContractAdapter: EVM 兼容链
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

logger = logging.getLogger("trc8004.adapter")


class ContractAdapter:
    """
    合约适配器抽象基类

    定义与区块链合约交互的标准接口。
    """

    def call(self, contract: str, method: str, params: List[Any]) -> Any:
        """
        调用合约只读方法

        Args:
            contract: 合约名称 ("identity", "validation", "reputation")
            method: 方法名
            params: 参数列表

        Returns:
            调用结果
        """
        raise NotImplementedError

    def send(self, contract: str, method: str, params: List[Any], signer: Signer) -> str:
        """
        发送合约交易

        Args:
            contract: 合约名称
            method: 方法名
            params: 参数列表
            signer: 签名器

        Returns:
            交易 ID
        """
        raise NotImplementedError


class DummyContractAdapter(ContractAdapter):
    """
    本地测试用适配器

    返回确定性的交易 ID，不进行实际的区块链交互。
    适用于单元测试和本地开发。
    """

    def call(self, contract: str, method: str, params: List[Any]) -> Any:
        return {"contract": contract, "method": method, "params": params}

    def send(self, contract: str, method: str, params: List[Any], signer: Signer) -> str:
        stamp = int(time.time() * 1000)
        return f"0x{contract}-{method}-{stamp}"


class TronContractAdapter(ContractAdapter):
    """
    TRON 区块链合约适配器

    使用 tronpy 库与 TRON 区块链交互。

    Args:
        rpc_url: TRON RPC 节点地址
        identity_registry: IdentityRegistry 合约地址
        validation_registry: ValidationRegistry 合约地址
        reputation_registry: ReputationRegistry 合约地址
        fee_limit: 交易费用上限（单位：sun）
        retry_config: 重试配置

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
        """获取或创建 TRON 客户端"""
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
        """解析合约地址并获取合约引用"""
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
            
            # 如果提供了 ABI 文件路径，使用文件中的 ABI（支持 ABIEncoderV2）
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
                # 没有提供 ABI 文件，尝试修复 ABIEncoderV2 的 tuple 类型
                # tronpy 不支持 components 字段，需要手动展开
                fixed_abi = self._fix_abi_encoder_v2(contract_ref.abi)
                if fixed_abi:
                    contract_ref.abi = fixed_abi
                    logger.debug("Fixed ABIEncoderV2 for %s", contract)
        except Exception as e:
            raise ContractCallError(contract, "get_contract", str(e)) from e

        return contract_ref

    def _fix_abi_encoder_v2(self, abi: list) -> list:
        """
        修复 ABIEncoderV2 的 tuple 类型
        
        tronpy 不支持 components 字段，需要将 tuple 类型展开为基本类型
        注意：链上返回的 type 可能是 "Function" 而不是 "function"
        """
        if not abi:
            return abi
        
        def expand_type(item: dict) -> str:
            """展开 tuple 类型为 (type1,type2,...) 格式"""
            t = item.get("type", "")
            if t == "tuple" or t.startswith("tuple["):
                components = item.get("components", [])
                if components:
                    inner = ",".join(expand_type(c) for c in components)
                    if t == "tuple":
                        return f"({inner})"
                    else:
                        # tuple[] -> (...)[]
                        suffix = t[5:]  # 获取 [] 部分
                        return f"({inner}){suffix}"
            return t
        
        fixed = []
        for entry in abi:
            # 使用 .lower() 进行大小写不敏感比较
            if entry.get("type", "").lower() != "function":
                fixed.append(entry)
                continue
            
            new_entry = dict(entry)
            
            # 修复 inputs
            if "inputs" in entry:
                new_inputs = []
                for inp in entry["inputs"]:
                    new_inp = dict(inp)
                    new_inp["type"] = expand_type(inp)
                    # 移除 components 字段，tronpy 不需要
                    new_inp.pop("components", None)
                    new_inputs.append(new_inp)
                new_entry["inputs"] = new_inputs
            
            # 修复 outputs
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
        """选择合约方法（处理重载）"""

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

        # 处理 register 方法的重载
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
        """调用合约只读方法"""
        contract_ref = self._resolve_contract(contract)
        function = self._pick_function(contract_ref, method, params)
        try:
            result = function(*params)
            # tronpy 的 ContractMethod 在某些情况下直接返回结果
            # 而不是返回一个需要 .call() 的对象
            if hasattr(result, 'call'):
                return result.call()
            return result
        except Exception as e:
            raise ContractCallError(contract, method, str(e)) from e

    def send(self, contract: str, method: str, params: List[Any], signer: Signer) -> str:
        """
        发送合约交易（带重试）

        Args:
            contract: 合约名称
            method: 方法名
            params: 参数列表
            signer: 签名器

        Returns:
            交易 ID

        Raises:
            ContractCallError: 合约调用失败
            TransactionFailedError: 交易执行失败
            InsufficientEnergyError: 能量不足
        """
        return self._send_with_retry(contract, method, params, signer)

    @retry(operation_name="contract_send")
    def _send_with_retry(
        self, contract: str, method: str, params: List[Any], signer: Signer
    ) -> str:
        """带重试的交易发送"""
        contract_ref = self._resolve_contract(contract)

        # 检查能量（仅 register 方法）
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
            # 尝试使用标准方式构建交易
            try:
                txn = function(*params).with_owner(signer.get_address()).build()
            except ValueError as ve:
                if "ABIEncoderV2" in str(ve):
                    # ABIEncoderV2 需要手动编码参数
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
            # 网络错误可重试
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
        使用 eth_abi 手动编码 ABIEncoderV2 参数
        
        tronpy 不支持 ABIEncoderV2 的 tuple 类型，需要手动编码参数并构建交易
        """
        try:
            from eth_abi import encode
            from eth_utils import keccak
        except ImportError:
            raise RuntimeError("eth_abi and eth_utils are required for ABIEncoderV2 encoding")
        
        # 找到方法的 ABI（支持重载方法）
        # 注意：链上返回的 type 可能是 "Function" 而不是 "function"
        method_abi = None
        for item in contract_ref.abi:
            if item.get("type", "").lower() == "function" and item.get("name") == method:
                inputs = item.get("inputs", [])
                if len(inputs) == len(params):
                    method_abi = item
                    break
        
        if not method_abi:
            # 打印调试信息
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
        
        # 构建类型签名
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
        
        # 编码参数
        encoded_params = encode(types, params)
        
        # 计算函数选择器 (keccak256 of function signature)
        sig = f"{method}({','.join(types)})"
        selector = keccak(text=sig)[:4]
        logger.debug("Function signature: %s, selector: %s", sig, selector.hex())
        
        # 构建完整的 calldata
        data = selector + encoded_params
        
        # 使用 tronpy 的底层 API 构建交易
        client = self._get_client()
        owner_address = signer.get_address()
        
        # 构建 TriggerSmartContract 交易
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
        """检查账户能量"""
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
