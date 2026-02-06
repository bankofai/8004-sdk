#!/usr/bin/env python3
"""
TRC-8004 SDK 快速入门示例

运行前请设置环境变量:
    export TRON_PRIVATE_KEY="your_hex_private_key"
    export TRON_RPC_URL="https://nile.trongrid.io"
    export IDENTITY_REGISTRY="TYourIdentityRegistryAddress"

运行:
    python examples/quickstart.py
"""

import os
import time
from sdk import AgentSDK
from sdk.exceptions import SDKError, InsufficientEnergyError

def main():
    # 1. 初始化 SDK
    print("🚀 初始化 SDK...")
    sdk = AgentSDK(
        private_key=os.getenv("TRON_PRIVATE_KEY"),
        rpc_url=os.getenv("TRON_RPC_URL", "https://nile.trongrid.io"),
        network="tron:nile",
        identity_registry=os.getenv("IDENTITY_REGISTRY"),
        validation_registry=os.getenv("VALIDATION_REGISTRY"),
        reputation_registry=os.getenv("REPUTATION_REGISTRY"),
    )
    print(f"   ✓ SDK 初始化完成，网络: {sdk.config.network}")

    # 2. 构建订单承诺 (不需要链上交互)
    print("\n📝 构建订单承诺...")
    order_params = {
        "asset": "TRX/USDT",
        "amount": 100.0,
        "slippage": 0.01,
        "type": "market_order",
        "nonce": f"demo-{int(time.time())}",
    }
    commitment = sdk.build_commitment(order_params)
    print(f"   ✓ 承诺哈希: {commitment[:20]}...")

    # 3. 计算请求哈希
    print("\n🔐 计算请求哈希...")
    request_payload = {
        "actionCommitment": commitment,
        "orderParams": order_params,
        "timestamp": int(time.time()),
    }
    request_hash = sdk.compute_request_hash(request_payload)
    print(f"   ✓ 请求哈希: {request_hash[:20]}...")

    # 4. 规范化 JSON (用于存储/传输)
    print("\n📦 规范化 JSON...")
    canonical = sdk.dump_canonical(request_payload)
    print(f"   ✓ 规范化长度: {len(canonical)} bytes")

    # 5. 链上操作示例 (需要私钥和合约地址)
    if os.getenv("TRON_PRIVATE_KEY") and os.getenv("IDENTITY_REGISTRY"):
        print("\n⛓️  链上操作示例...")
        try:
            # 注册 Agent (如果尚未注册)
            # tx_id = sdk.register_agent(
            #     token_uri="https://example.com/my-agent.json",
            #     metadata=[{"key": "name", "value": "DemoAgent"}],
            # )
            # print(f"   ✓ Agent 注册交易: {tx_id}")
            print("   ⚠️  跳过链上注册 (取消注释上面代码以执行)")
        except InsufficientEnergyError:
            print("   ❌ 能量不足，请充值 TRX")
        except SDKError as e:
            print(f"   ❌ SDK 错误: {e}")
    else:
        print("\n⚠️  跳过链上操作 (未设置 TRON_PRIVATE_KEY 或 IDENTITY_REGISTRY)")

    print("\n✅ 快速入门完成!")
    print("\n下一步:")
    print("  1. 查看 README.md 了解完整 API")
    print("  2. 运行 examples/register_agent.py 注册你的 Agent")
    print("  3. 运行 examples/validation_flow.py 体验验证流程")


if __name__ == "__main__":
    main()
