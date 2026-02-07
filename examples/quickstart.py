#!/usr/bin/env python3
"""
TRON-8004 SDK Quickstart Example

Please set environment variables before running:
    export TRON_PRIVATE_KEY="your_hex_private_key"
    export TRON_RPC_URL="https://nile.trongrid.io"
    export IDENTITY_REGISTRY="TYourIdentityRegistryAddress"

Run:
    python examples/quickstart.py
"""

import os
import time
from sdk import AgentSDK
from sdk.exceptions import SDKError, InsufficientEnergyError

def main():
    # 1. Initialize SDK
    print("🚀 Initializing SDK...")
    sdk = AgentSDK(
        private_key=os.getenv("TRON_PRIVATE_KEY"),
        rpc_url=os.getenv("TRON_RPC_URL", "https://nile.trongrid.io"),
        network="tron:nile",
        identity_registry=os.getenv("IDENTITY_REGISTRY"),
        validation_registry=os.getenv("VALIDATION_REGISTRY"),
        reputation_registry=os.getenv("REPUTATION_REGISTRY"),
    )
    print(f"   ✓ SDK Initialized, network: {sdk.config.network}")

    # 2. Build Order Commitment (No on-chain interaction required)
    print("\n📝 Building Order Commitment...")
    order_params = {
        "asset": "TRX/USDT",
        "amount": 100.0,
        "slippage": 0.01,
        "type": "market_order",
        "nonce": f"demo-{int(time.time())}",
    }
    commitment = sdk.build_commitment(order_params)
    print(f"   ✓ Commitment Hash: {commitment[:20]}...")

    # 3. Compute Request Hash
    print("\n🔐 Computing Request Hash...")
    request_payload = {
        "actionCommitment": commitment,
        "orderParams": order_params,
        "timestamp": int(time.time()),
    }
    request_hash = sdk.compute_request_hash(request_payload)
    print(f"   ✓ Request Hash: {request_hash[:20]}...")

    # 4. Normalize JSON (for storage/transmission)
    print("\n📦 Normalizing JSON...")
    canonical = sdk.dump_canonical(request_payload)
    print(f"   ✓ Normalized Length: {len(canonical)} bytes")

    # 5. On-chain Operation Example (Requires Private Key and Contract Address)
    if os.getenv("TRON_PRIVATE_KEY") and os.getenv("IDENTITY_REGISTRY"):
        print("\n⛓️  On-chain Operation Example...")
        try:
            # Register Agent (if not registered)
            # tx_id = sdk.register_agent(
            #     token_uri="https://example.com/my-agent.json",
            #     metadata=[{"key": "name", "value": "DemoAgent"}],
            # )
            # print(f"   ✓ Agent Registration TX: {tx_id}")
            print("   ⚠️  Skipping on-chain registration (Uncomment above code to execute)")
        except InsufficientEnergyError:
            print("   ❌ Insufficient Energy, please charge TRX")
        except SDKError as e:
            print(f"   ❌ SDK Error: {e}")
    else:
        print("\n⚠️  Skipping on-chain operation (TRON_PRIVATE_KEY or IDENTITY_REGISTRY not set)")

    print("\n✅ Quickstart Complete!")
    print("\nNext Steps:")
    print("  1. Check README.md for full API documentation")
    print("  2. Run examples/register_agent.py to register your Agent")
    print("  3. Run examples/validation_flow.py to experience the validation flow")


if __name__ == "__main__":
    main()
