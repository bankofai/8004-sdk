---
inclusion: always
---

# TRC-8004 SDK 开发指南 (Jan 2026 Update)

## 概述

TRC-8004 SDK 提供 Agent 与链上合约交互的统一接口，支持：
- 身份注册与元数据管理 (IdentityRegistry)
- 验证请求与响应 (ValidationRegistry)
- 信誉反馈提交 (ReputationRegistry)

## 合约地址 (Nile Testnet)

```
IdentityRegistry:   TRLTghbBbxEmB2BojVfk5EugUrTARSkeU4
ReputationRegistry: TPXCSyfNi5G2UTQMXdr8PTWS2RXp3tPbU7
ValidationRegistry: TTtRQ7csbUaWbFaJim5Lxp4RkkWiaj2dE3
```

## Jan 2026 关键变更

### 1. feedbackAuth 已移除 ❌

旧版本需要预授权签名才能提交反馈，现在直接提交：

```python
# ✅ Jan 2026 - 直接提交
tx_id = sdk.submit_reputation(
    agent_id=1,
    score=95,
    tag1="execution",      # string 类型
    tag2="market-swap",    # string 类型
    endpoint="/a2a/x402/execute",  # 新参数
)

# ❌ 旧版本 - 已弃用
# sdk.submit_reputation(agent_id, score, feedback_auth=auth)
```

### 2. tag 类型改为 string

ValidationRegistry 和 ReputationRegistry 的 tag 参数从 `bytes32` 改为 `string`：

```python
# validation_response
sdk.validation_response(
    request_hash="0x...",
    response=95,
    tag="test-validation",  # string，不是 bytes32
)

# submit_reputation
sdk.submit_reputation(
    agent_id=1,
    score=88,
    tag1="execution",   # string
    tag2="market-swap", # string
)
```

### 3. 新增方法

```python
# IdentityRegistry
sdk.set_agent_uri(agent_id, new_uri)  # 更新 Agent URI
sdk.set_agent_wallet(agent_id, wallet, deadline, wallet_signer)  # 需要 EIP-712 签名
sdk.get_agent_wallet(agent_id)

# ValidationRegistry
sdk.request_exists(request_hash)
sdk.get_validation_status(request_hash)
sdk.get_validation_request(request_hash)
sdk.get_validation_summary(agent_id, validator_addresses, tag)
sdk.get_agent_validations(agent_id)
sdk.get_validator_requests(validator_address)
```

### 4. build_feedback_auth 已弃用

```python
# ⚠️ 会触发 DeprecationWarning
sdk.build_feedback_auth(...)  # 不要使用
```

## 核心 API

### AgentSDK 初始化

```python
from sdk import AgentSDK

sdk = AgentSDK(
    private_key="your_hex_private_key",
    rpc_url="https://nile.trongrid.io",
    network="tron:nile",
    identity_registry="TRLTghbBbxEmB2BojVfk5EugUrTARSkeU4",
    validation_registry="TTtRQ7csbUaWbFaJim5Lxp4RkkWiaj2dE3",
    reputation_registry="TPXCSyfNi5G2UTQMXdr8PTWS2RXp3tPbU7",
    fee_limit=100_000_000,
)
```

### 注册 Agent

```python
tx_id = sdk.register_agent(
    token_uri="https://example.com/agent.json",
    metadata=[
        {"key": "name", "value": "MyAgent"},
        {"key": "version", "value": "1.0.0"},
    ],
)
```

### 验证流程

```python
# 1. 发起验证请求 (由 Agent owner 调用)
tx_id = sdk.validation_request(
    validator_addr="TValidator...",
    agent_id=1,
    request_uri="ipfs://Qm...",
    request_hash="0x...",
)

# 2. 提交验证响应 (由 Validator 调用)
tx_id = sdk.validation_response(
    request_hash="0x...",
    response=95,
    response_uri="ipfs://Qm...",
    tag="market-swap",
)
```

### 信誉反馈

```python
# 直接提交反馈 (无需预授权)
tx_id = sdk.submit_reputation(
    agent_id=1,
    score=88,
    tag1="execution",
    tag2="market-swap",
    endpoint="/a2a/x402/execute",
    feedback_uri="ipfs://Qm...",
)

# 查询汇总
summary = sdk.get_feedback_summary(
    agent_id=1,
    client_addresses=["TClient..."],  # 可选过滤
    tag1="execution",
)
# => {"count": 10, "averageScore": 92}
```

## 文件结构

```
trc-8004-sdk/
├── src/sdk/
│   ├── agent_sdk.py      # 主 SDK 类
│   ├── contract_adapter.py  # 合约适配器
│   ├── signer.py         # 签名器
│   ├── exceptions.py     # 异常定义
│   └── retry.py          # 重试逻辑
├── tests/
│   └── test_agent_sdk.py
└── examples/
    └── quickstart.py
```

## 测试

```bash
PYTHONPATH=src python -m pytest tests/ -v
```
