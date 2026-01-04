# trc-8004-sdk

这是一个用于本地开发的 TRC-8004 SDK。

- commitment 与 request_hash 使用 keccak256 (sha3_256)。
- TRON 链上调用使用 `tronpy`（需要配置 registry 合约地址）。
- 转账由 Agent 自行实现，不由 SDK 负责。

## 目录结构
- `src/sdk/agent_sdk.py`: 主类 `AgentSDK`
- `src/sdk/signer.py`: signer 接口 + 默认 signer
- `src/sdk/contract_adapter.py`: 合约适配器接口 + TRON 适配器

## 安装/验证
```bash
cd trc-8004-sdk
uv run python -c "from sdk import AgentSDK; print(AgentSDK)"
```

## 基本用法
```python
from sdk import AgentSDK

sdk = AgentSDK(private_key="dev-key")

request_tx = sdk.validation_request(
    validator_addr="TValidator",
    agent_id=1,
    request_uri="ipfs://Qm...",
    request_hash="0x...",
)
print(request_tx)
```

## TRON 配置（ERC-8004 对齐）
```python
from sdk import AgentSDK

sdk = AgentSDK(
    private_key="hex_private_key",
    rpc_url="https://nile.trongrid.io",
    network="tron:nile",
    identity_registry="TIdentityRegistry",
    validation_registry="TValidationRegistry",
    reputation_registry="TReputationRegistry",
)
```

## 示例：构建 commitment 与 request_hash
```python
from sdk import AgentSDK

sdk = AgentSDK(private_key="dev-key")

order_params = {
    "asset": "TRX/USDT",
    "amount": 100.0,
    "slippage": 0.01,
    "type": "market_order",
    "nonce": "uuid-hex",
}

commitment = sdk.build_commitment(order_params)
request_hash = sdk.compute_request_hash("request payload or uri content")
signature = sdk.build_a2a_signature(commitment, 1710000000, sdk.signer.get_address())

print(commitment, request_hash, signature)
```

## 示例：支付签名
```python
from sdk import AgentSDK

sdk = AgentSDK(private_key="dev-key")

signature = sdk.build_payment_signature(
    action_commitment="0xcommitment",
    payment_address="TMarketAgentPayAddr",
    amount="12.50",
    timestamp=1710000000,
)

print(signature)
```

## 示例：构建 A2A payload
```python
from sdk import AgentSDK

sdk = AgentSDK(private_key="dev-key")

order_params = {
    "asset": "TRX/USDT",
    "amount": 100.0,
    "slippage": 0.01,
    "type": "market_order",
    "nonce": "uuid-hex",
}

quote_payload = sdk.build_market_order_quote_request("TRX/USDT", 100.0, 0.01)
new_payload = sdk.build_market_order_new_request("TRX/USDT", 100.0, "0xpayment", 0.01)
x402_quote_payload = sdk.build_x402_quote_request(order_params)
x402_execute_payload = sdk.build_x402_execute_request(
    action_commitment=sdk.build_commitment(order_params),
    order_params=order_params,
    payment_tx_hash="0xagentpayment",
    timestamp=1710000000,
    caller_address=sdk.signer.get_address(),
)

print(quote_payload, new_payload, x402_quote_payload, x402_execute_payload)
```

## Hello World：用 SDK 构建一个最小 Agent
下面是一个最小的 FastAPI Agent 示例：

```python
from fastapi import FastAPI
from sdk import AgentSDK

app = FastAPI(title="HelloAgent")
sdk = AgentSDK(private_key="dev-key")

@app.get("/hello")
def hello():
    message = {
        "message": "hello world",
        "signer": sdk.signer.get_address(),
    }
    return message
```

运行方式：
```bash
uv run uvicorn app:app --host 0.0.0.0 --port 9000
```
