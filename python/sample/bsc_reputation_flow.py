"""BSC reputation flow: register -> giveFeedback -> readFeedback -> summary.

Set private keys in this file before running.
"""

import time

from bankofai.sdk_8004.core.sdk import SDK


# Replace before running.
OWNER_PRIVATE_KEY = "<EVM_OWNER_PRIVATE_KEY>"
REVIEWER_PRIVATE_KEY = "<EVM_REVIEWER_PRIVATE_KEY>"

if OWNER_PRIVATE_KEY.startswith("<") or REVIEWER_PRIVATE_KEY.startswith("<"):
    raise SystemExit("Set OWNER_PRIVATE_KEY and REVIEWER_PRIVATE_KEY in sample/bsc_reputation_flow.py first")

sdk_owner = SDK(
    chainId=97,
    rpcUrl="https://data-seed-prebsc-1-s1.binance.org:8545",
    network="evm:bsc",
    signer=OWNER_PRIVATE_KEY,
)

sdk_reviewer = SDK(
    chainId=97,
    rpcUrl="https://data-seed-prebsc-1-s1.binance.org:8545",
    network="evm:bsc",
    signer=REVIEWER_PRIVATE_KEY,
)

agent = sdk_owner.createAgent(
    name=f"Sample BSC Rep Agent {int(time.time())}",
    description="sample bsc reputation flow",
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

reg = agent.register("https://example.com/agent-card.json").wait_confirmed(timeout=180).result
print("registered:", reg.agentId)

fb_handle = sdk_reviewer.giveFeedback(
    agentId=reg.agentId,
    value=89,
    tag1="execution",
    tag2="market-swap",
    endpoint="/a2a/x402/execute",
)
print("feedback_tx:", fb_handle.tx_hash)
fb = fb_handle.wait_confirmed(timeout=180).result
print("feedback_id:", fb.id)

agent_num = int(str(reg.agentId).split(":")[-1])
reviewer = sdk_reviewer.web3_client.account.address
idx = sdk_reviewer.web3_client.call_contract(
    sdk_reviewer.reputation_registry,
    "getLastIndex",
    agent_num,
    reviewer,
)

fb_read = sdk_reviewer.getFeedback(reg.agentId, reviewer, int(idx))
print("feedback_read:", fb_read.value, fb_read.tags, fb_read.isRevoked)

summary = sdk_reviewer.getReputationSummary(reg.agentId)
print("summary:", summary)
