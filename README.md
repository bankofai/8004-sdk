# TRC-8004 Agent SDK

去中心化 Agent 协作的 Python SDK，实现 ERC-8004 (Trustless Agent Protocol) 规范。

## 特性

- 🔗 **多链支持**：抽象的 Adapter 架构，当前支持 TRON，可扩展 EVM 链
- 🔄 **自动重试**：可配置的指数退避重试策略
- 🛡️ **类型安全**：完整的类型注解和 Pydantic 校验
- 📝 **详细日志**：结构化日志便于调试
- ⚡ **异步支持**：同时提供同步和异步 API

## 安装

```bash
# 使用 uv
uv add trc-8004-sdk

# 使用 pip
pip install trc-8004-sdk
```

## 快速开始

```python
from sdk import AgentSDK

# 初始化 SDK
sdk = AgentSDK(
    private_key="your_hex_private_key",
    rpc_url="https://nile.trongrid.io",
    network="tron:nile",
    identity_registry="TIdentityRegistryAddress",
    validation_registry="TValidationRegistryAddress",
    reputation_registry="TReputationRegistryAddress",
)

# 注册 Agent
tx_id = sdk.register_agent(
    token_uri="https://example.com/agent.json",
    metadata=[{"key": "name", "value": "MyAgent"}],
)
print(f"Agent registered: {tx_id}")

# 构建订单承诺
commitment = sdk.build_commitment({
    "asset": "TRX/USDT",
    "amount": 100.0,
    "slippage": 0.01,
})
```

## 核心功能

### 1. 身份注册 (IdentityRegistry)

```python
# 注册新 Agent
tx_id = sdk.register_agent(
    token_uri="https://example.com/agent.json",
    metadata=[
        {"key": "name", "value": "MyAgent"},
        {"key": "version", "value": "1.0.0"},
    ],
)

# 更新元数据
tx_id = sdk.update_metadata(
    agent_id=1,
    key="description",
    value="Updated description",
)
```

### 2. 验证请求 (ValidationRegistry)

```python
# 发起验证请求
tx_id = sdk.validation_request(
    validator_addr="TValidatorAddress",
    agent_id=1,
    request_uri="ipfs://QmXxx...",
    request_hash="0x" + "aa" * 32,
)

# 提交验证响应（验证者调用）
tx_id = sdk.validation_response(
    request_hash="0x" + "aa" * 32,
    response=95,  # 0-100 评分
    response_uri="ipfs://QmYyy...",
)
```

### 3. 信誉反馈 (ReputationRegistry)

```python
# 提交信誉反馈
tx_id = sdk.submit_reputation(
    agent_id=1,
    score=95,
    tag1="0x" + "11" * 32,  # 可选标签
    feedback_auth="0x...",   # Agent 提供的授权签名
)
```

### 4. 签名构建

```python
# 构建 A2A 请求签名
signature = sdk.build_a2a_signature(
    action_commitment="0x...",
    timestamp=int(time.time()),
    caller_address="TCallerAddress",
)

# 构建反馈授权
feedback_auth = sdk.build_feedback_auth(
    agent_id=1,
    client_addr="TClientAddress",
    index_limit=10,
    expiry=int(time.time()) + 3600,
    chain_id=None,  # 自动解析
    identity_registry="TIdentityRegistry",
)
```

### 5. 请求构建辅助

```python
# 市价单报价请求
quote_req = sdk.build_market_order_quote_request(
    asset="TRX/USDT",
    amount=100.0,
    slippage=0.01,
)

# X402 执行请求
execute_req = sdk.build_x402_execute_request(
    action_commitment="0x...",
    order_params={"asset": "TRX/USDT", "amount": 100.0},
    payment_tx_hash="0x...",
    timestamp=int(time.time()),
    caller_address="TCallerAddress",
)
```

## 重试配置

SDK 提供可配置的重试策略：

```python
from sdk import AgentSDK, RetryConfig, AGGRESSIVE_RETRY_CONFIG

# 使用预定义配置
sdk = AgentSDK(
    private_key="...",
    retry_config=AGGRESSIVE_RETRY_CONFIG,  # 5 次重试
)

# 自定义配置
custom_config = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
)
sdk = AgentSDK(private_key="...", retry_config=custom_config)
```

预定义配置：
- `DEFAULT_RETRY_CONFIG`: 3 次重试，1s 基础延迟
- `AGGRESSIVE_RETRY_CONFIG`: 5 次重试，0.5s 基础延迟
- `CONSERVATIVE_RETRY_CONFIG`: 2 次重试，2s 基础延迟
- `NO_RETRY_CONFIG`: 不重试

## 异常处理

SDK 提供细粒度的异常类型：

```python
from sdk import (
    SDKError,
    ContractCallError,
    TransactionFailedError,
    RetryExhaustedError,
    InsufficientEnergyError,
)

try:
    tx_id = sdk.register_agent(token_uri="...")
except InsufficientEnergyError:
    print("账户能量不足，请充值")
except RetryExhaustedError as e:
    print(f"重试耗尽: {e.last_error}")
except ContractCallError as e:
    print(f"合约调用失败: {e.code} - {e.details}")
except SDKError as e:
    print(f"SDK 错误: {e}")
```

异常层级：
```
SDKError
├── ConfigurationError
│   ├── MissingContractAddressError
│   ├── InvalidPrivateKeyError
│   └── ChainIdResolutionError
├── NetworkError
│   ├── RPCError
│   ├── TimeoutError
│   └── RetryExhaustedError
├── ContractError
│   ├── ContractCallError
│   ├── ContractFunctionNotFoundError
│   ├── TransactionFailedError
│   └── InsufficientEnergyError
├── SignatureError
│   ├── InvalidSignatureError
│   └── SignerNotAvailableError
├── DataError
│   ├── InvalidAddressError
│   ├── InvalidHashError
│   ├── SerializationError
│   └── DataLoadError
└── ValidationError
    ├── RequestHashMismatchError
    ├── FeedbackAuthExpiredError
    └── FeedbackAuthInvalidError
```

## HTTP 客户端

### AgentClient

智能 HTTP 客户端，自动解析 Agent 元数据中的端点：

```python
from sdk import AgentClient

client = AgentClient(
    metadata=agent_metadata,  # 从 Central Service 获取
    base_url="https://agent.example.com",
)

# 自动解析端点并发送请求
response = client.post("quote", {"asset": "TRX/USDT", "amount": 100})
```

### AgentProtocolClient

Agent Protocol 标准客户端：

```python
from sdk import AgentProtocolClient

client = AgentProtocolClient(base_url="https://agent.example.com")

# 创建任务并执行
result = client.run({
    "skill": "market_order",
    "params": {"asset": "TRX/USDT", "amount": 100},
})
```

## 链工具

```python
from sdk import load_request_data, fetch_event_logs

# 加载请求数据（支持 file://, ipfs://, http://）
data = load_request_data("ipfs://QmXxx...")

# 获取链上事件
events = fetch_event_logs(
    client=tron_client,
    contract_address="TValidationRegistry",
    event_name="ValidationRequest",
    from_block=1000000,
    to_block=1001000,
)
```

## 扩展多链支持

SDK 使用 Adapter 模式，可轻松扩展其他链：

```python
from sdk import ContractAdapter, Signer

class EVMContractAdapter(ContractAdapter):
    def __init__(self, rpc_url: str, ...):
        from web3 import Web3
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
    
    def send(self, contract: str, method: str, params: list, signer: Signer) -> str:
        # EVM 交易逻辑
        ...

class EVMSigner(Signer):
    def __init__(self, private_key: str):
        from eth_account import Account
        self.account = Account.from_key(private_key)
    
    def sign_message(self, payload: bytes) -> str:
        # EIP-191 签名
        ...
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TRON_RPC_URL` | TRON RPC 节点 | `https://nile.trongrid.io` |
| `TRON_NETWORK` | 网络标识 | `tron:nile` |
| `IDENTITY_REGISTRY` | IdentityRegistry 地址 | - |
| `VALIDATION_REGISTRY` | ValidationRegistry 地址 | - |
| `REPUTATION_REGISTRY` | ReputationRegistry 地址 | - |
| `TRON_FEE_LIMIT` | 交易费用上限 (sun) | `10000000` |
| `IPFS_GATEWAY_URL` | IPFS 网关 | `https://ipfs.io/ipfs` |

## 开发

```bash
# 安装依赖
uv sync

# 运行测试
uv run pytest

# 类型检查
uv run mypy src/sdk
```

## License

MIT
