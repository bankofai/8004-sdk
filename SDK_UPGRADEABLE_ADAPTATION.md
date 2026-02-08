# SDK 适配 Upgradeable 合约改动清单

本文档列出 **SDK 为适配 Upgradeable 合约**所需的**具体改动**，适用合约目录：

`/Users/bobo/code/8004/tron-8004-contracts/contracts`

包含合约：
- `IdentityRegistryUpgradeable.sol`
- `ReputationRegistryUpgradeable.sol`
- `ValidationRegistryUpgradeable.sol`

当前 SDK 代码位置：
- `tron-8004-sdk/src/sdk/agent_sdk.py`
- `tron-8004-sdk/src/sdk/contract_adapter.py`

---

## 1. IdentityRegistryUpgradeable – 必须改动

### 1.1 EIP‑712 域名/版本不一致
**合约使用**
- name: `ERC8004IdentityRegistry`
- version: `1`

**SDK 当前使用**
- name: `ERC-8004 IdentityRegistry`
- version: `1.1`

**改动**
- 在 `AgentSDK._build_eip712_wallet_signature()` 中替换为：
  - name: `ERC8004IdentityRegistry`
  - version: `1`

**涉及文件**
- `tron-8004-sdk/src/sdk/agent_sdk.py`

---

### 1.2 setAgentWallet 的 TypeHash 不一致
**合约 typehash**
```
AgentWalletSet(uint256 agentId,address newWallet,address owner,uint256 deadline)
```

**SDK 当前 typehash**
```
SetAgentWallet(uint256 agentId,address newWallet,uint256 deadline)
```

**改动**
- 变更 typehash 字符串为 `AgentWalletSet`
- struct hash 参数顺序改为：`agentId, newWallet, owner, deadline`

**涉及文件**
- `tron-8004-sdk/src/sdk/agent_sdk.py`

---

### 1.3 deadline 受 5 分钟上限约束
**合约规则**
```
require(deadline <= block.timestamp + 5 minutes, "deadline too far");
```

**改动**
- SDK 在 `set_agent_wallet(...)` 内校验 `deadline <= now + 300`
- 提前报错，避免链上 revert

**涉及文件**
- `tron-8004-sdk/src/sdk/agent_sdk.py`

---

### 1.4 agentWallet 写入路径限制
**合约行为**
- `register(...)` 自动写入 `agentWallet = msg.sender`
- `setMetadata("agentWallet", ...)` 被禁止

**改动**
- SDK 不再允许通过 `set_metadata` 写 `agentWallet`
- 仅允许 `set_agent_wallet(...)`

**涉及文件**
- `tron-8004-sdk/src/sdk/agent_sdk.py`

---

### 1.5 缺少 unsetAgentWallet
**合约提供**
```
function unsetAgentWallet(uint256 agentId)
```

**改动**
- SDK 增加 `unset_agent_wallet(agent_id)` 封装

**涉及文件**
- `tron-8004-sdk/src/sdk/agent_sdk.py`

---

## 2. ReputationRegistryUpgradeable – 必须改动

### 2.1 giveFeedback 参数签名变更
**合约签名**
```
giveFeedback(
  uint256 agentId,
  int128 value,
  uint8 valueDecimals,
  string tag1,
  string tag2,
  string endpoint,
  string feedbackURI,
  bytes32 feedbackHash
)
```

**SDK 当前**
- `submit_reputation(agent_id, score, tag1, tag2, endpoint, feedback_uri, feedback_hash)`
- `score` 仅支持 0–100

**改动**
- 以 `value + value_decimals` 作为主接口
- 如需兼容旧用法，可保留 helper：
  - `submit_score(agent_id, score, ...)` → `value=score, value_decimals=0`

**涉及文件**
- `tron-8004-sdk/src/sdk/agent_sdk.py`

---

### 2.2 readFeedback 返回结构变化
**合约返回**
```
(int128 value, uint8 valueDecimals, string tag1, string tag2, bool isRevoked)
```

**SDK 当前解析**
```
(score, tag1, tag2, isRevoked)
```

**改动**
- 更新 `read_feedback(...)` 解析：
  - `value`
  - `value_decimals`
  - `tag1`
  - `tag2`
  - `is_revoked`

**涉及文件**
- `tron-8004-sdk/src/sdk/agent_sdk.py`

---

### 2.3 getSummary 返回结构变化
**合约返回**
```
(uint64 count, int128 summaryValue, uint8 summaryValueDecimals)
```

**SDK 当前**
```
{count, averageScore}
```

**改动**
- 输出字段改为：
  - `count`
  - `summaryValue`
  - `summaryValueDecimals`
- 如需 `averageScore`，在 SDK/上层自行换算

**涉及文件**
- `tron-8004-sdk/src/sdk/agent_sdk.py`

---

### 2.4 getSummary 强制要求 clientAddresses 非空
**合约逻辑**
```
if clientAddresses.length == 0) revert("clientAddresses required");
```

**改动**
- SDK 在 `get_feedback_summary(...)` 强制要求 `client_addresses` 非空
- 为空时直接报错

**涉及文件**
- `tron-8004-sdk/src/sdk/agent_sdk.py`

---

## 3. ValidationRegistryUpgradeable – 必须改动

### 3.1 不再提供 requestExists / getRequest
Upgradeable 合约 **没有**：
- `requestExists`
- `getRequest`

**改动**
- 移除或加版本判断：
  - `request_exists(...)`
  - `get_validation_request(...)`
- 如需要可改为事件查询

**涉及文件**
- `tron-8004-sdk/src/sdk/agent_sdk.py`

---

### 3.2 getValidationStatus 返回结构变化
**合约返回**
```
(validatorAddress, agentId, response, responseHash, tag, lastUpdate)
```

**SDK 当前**
```
(validatorAddress, agentId, response, tag, lastUpdate)
```

**改动**
- 更新解析，增加 `responseHash`
- 注意：`getValidationStatus` 对未知 `requestHash` 会直接 `revert("unknown")`，SDK 不能假设返回空值

**涉及文件**
- `tron-8004-sdk/src/sdk/agent_sdk.py`

---

### 3.3 requestURI/responseURI 仅存在于事件
Upgradeable 合约 **不存储 URI**，只在事件中出现。

**改动**
- SDK 若需 URI，必须通过 **事件索引** 或外部索引服务获取

---

## 4. TRON ABI / tronpy 兼容性

**问题**
- `register(agentURI, MetadataEntry[])` 涉及 tuple[]，tronpy 容易失败

**改动**
- 必须提供 ABI 文件并配置：
  - `IDENTITY_REGISTRY_ABI_PATH`
  - `REPUTATION_REGISTRY_ABI_PATH`
  - `VALIDATION_REGISTRY_ABI_PATH`

**涉及文件**
- `tron-8004-sdk/src/sdk/contract_adapter.py`

---

## 5. 兼容层（可选）

如果你需要同时兼容旧版合约：

- 增加 `contract_version` 参数（如 `"upgradeable-v2"`）
- 在 SDK 中进行条件分支：
  - `submit_reputation(score)` → 自动映射到 `value/valueDecimals`
  - 禁用旧版不存在的 read 方法

---

## 6. 总结清单（执行顺序）

Identity Registry：
- [ ] 修改 EIP‑712 域名/版本
- [ ] 修改 AgentWalletSet typehash 与字段顺序
- [ ] deadline 限制 5 分钟
- [ ] 增加 `unset_agent_wallet`

Reputation Registry：
- [ ] 改为 `value + valueDecimals`
- [ ] 更新 `read_feedback` 解析
- [ ] 更新 `get_feedback_summary` 解析
- [ ] 强制 clientAddresses 非空

Validation Registry：
- [ ] 移除/屏蔽 `request_exists` / `get_validation_request`
- [ ] 更新 `get_validation_status` 解析
- [ ] 需要 URI 时走事件/索引

TRON ABI：
- [ ] 配置 ABI 文件路径

---

如果你希望我直接动手改 SDK，请确认优先级或直接说“全部修改”。  
