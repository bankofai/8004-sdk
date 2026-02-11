"""Register an agent on BSC Testnet (chainId 97)."""

import time

from bankofai.sdk_8004.core.sdk import SDK


# Replace with your own key before running.
BSC_PRIVATE_KEY = "<EVM_PRIVATE_KEY>"

if BSC_PRIVATE_KEY.startswith("<"):
    raise SystemExit("Set BSC_PRIVATE_KEY in sample/bsc_register.py first")

sdk = SDK(
    chainId=97,
    rpcUrl="https://data-seed-prebsc-1-s1.binance.org:8545",
    network="evm:bsc",
    signer=BSC_PRIVATE_KEY,
)

agent = sdk.createAgent(
    name=f"Sample BSC Agent {int(time.time())}",
    description="sample register on bsc testnet",
    image="https://example.com/agent.png",
)

# Optional richer configuration
agent.setMCP("https://mcp.example.com/")
agent.setA2A("https://a2a.example.com/.well-known/agent-card.json")
agent.addSkill("data_engineering/data_transformation_pipeline", validate_oasf=True)
agent.addDomain("technology/data_science/data_science", validate_oasf=True)
agent.setTrust(reputation=True, cryptoEconomic=True)
agent.setMetadata({"version": "1.0.0", "category": "sample"})
agent.setActive(True)
agent.setX402Support(True)

handle = agent.register("https://example.com/agent-card.json")
print("tx_hash:", handle.tx_hash)
result = handle.wait_confirmed(timeout=180).result
print("agent_id:", result.agentId)
print("agent_uri:", result.agentURI)
