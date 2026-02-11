# BankOfAI 8004 SDK (Python)

Python SDK for agent identity, discovery, trust, and reputation based on 8004.

This SDK lets you register agents on-chain, attach MCP/A2A metadata, manage agent wallets, submit/read feedback, and run validation request/response flows across BSC and TRON.

## What Does This SDK Do?

BankOfAI 8004 SDK enables you to:

- Create and manage agent identities on-chain
- Register agent metadata using HTTP URI or IPFS (`register()` / `registerIPFS()`)
- Advertise MCP/A2A endpoints, skills, domains, trust models, and custom metadata
- Manage verified agent wallets with signature checks (`setWallet()` / `unsetWallet()`)
- Submit and read reputation feedback (`giveFeedback()`, `getFeedback()`, `searchFeedback()`, `getReputationSummary()`)
- Trigger and read validation flows (`validationRequest` / `validationResponse` / `getValidationStatus`)
- Work across EVM (BSC) and TRON networks with one SDK interface

## Network Support

- BSC Mainnet: `eip155:56`
- BSC Testnet: `eip155:97`
- TRON Mainnet: `mainnet` or `tron:mainnet`
- TRON Nile: `nile` or `tron:nile`
- TRON Shasta: `shasta` or `tron:shasta`

Entrypoint:

```python
from bankofai.sdk_8004.core.sdk import SDK
```

## Installation

### Prerequisites

- Python `>=3.11`
- `pip`
- Funded private key for write operations
- RPC endpoint for target chain

### Install from Source (Local)

Current release is local-install only (not published to PyPI yet).

```bash
git clone https://github.com/bankofai/8004-sdk.git
cd 8004-sdk/python
pip install -e .
```

## Quick Start

### 1. Initialize SDK

BSC Testnet:

```python
from bankofai.sdk_8004.core.sdk import SDK

sdk = SDK(
    rpcUrl="https://data-seed-prebsc-1-s1.binance.org:8545",
    network="eip155:97",
    signer="<EVM_PRIVATE_KEY>",
)
```

TRON Nile:

```python
from bankofai.sdk_8004.core.sdk import SDK

sdk = SDK(
    chainId=1,
    rpcUrl="https://nile.trongrid.io",
    network="nile",
    signer="<TRON_PRIVATE_KEY>",
    feeLimit=120_000_000,
)
```

### 2. Create and Register Agent

```python
agent = sdk.createAgent(
    name="My AI Agent",
    description="Demo agent",
    image="https://example.com/agent.png",
)

agent.setMCP("https://mcp.example.com/")
agent.setA2A("https://a2a.example.com/.well-known/agent-card.json")
agent.addSkill("data_engineering/data_transformation_pipeline", validate_oasf=True)
agent.addDomain("technology/data_science/data_science", validate_oasf=True)
agent.setTrust(reputation=True, cryptoEconomic=True)
agent.setMetadata({"version": "1.0.0", "category": "demo"})
agent.setActive(True)
agent.setX402Support(True)

tx = agent.register("https://example.com/agent-card.json")
res = tx.wait_confirmed(timeout=180).result
print(res.agentId, res.agentURI)
```

Optional IPFS registration:

```python
# Requires IPFS config in SDK initialization
# e.g. ipfs="pinata", pinataJwt="..."
tx = agent.registerIPFS()
res = tx.wait_confirmed(timeout=180).result
print(res.agentId, res.agentURI)
```

### 3. Load Existing Agent and Update

```python
agent = sdk.loadAgent("97:123")
agent.updateInfo(description="Updated description")
agent.setMetadata({"revision": "2"})

tx = agent.register("https://example.com/agent-card-v2.json")
print(tx.wait_confirmed(timeout=180).result.agentURI)
```

### 4. Wallet Management

```python
wallet = agent.getWallet()
print("current wallet:", wallet)

# setWallet requires signature from new wallet owner
set_tx = agent.setWallet("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb")
if set_tx:
    set_tx.wait_confirmed(timeout=180)

unset_tx = agent.unsetWallet()
if unset_tx:
    unset_tx.wait_confirmed(timeout=180)
```

### 5. Feedback and Reputation

```python
fb_tx = sdk.giveFeedback(
    agentId="97:1",
    value=88,
    tag1="execution",
    tag2="market-swap",
    endpoint="/a2a/x402/execute",
)
fb = fb_tx.wait_confirmed(timeout=180).result
print(fb.id)

record = sdk.getFeedback("97:1", "0xReviewerAddress", 1)
print(record.value, record.tags)

summary = sdk.getReputationSummary("97:1")
print(summary)
```

### 6. Validation Flow

```python
req_tx = sdk.validationRequest(
    validatorAddress="0xValidatorAddress",
    agentId="97:1",
    requestURI="ipfs://QmRequest",
)
req = req_tx.wait_confirmed(timeout=180).result

resp_tx = sdk.validationResponse(
    requestHash=req.requestHash,
    response=95,
    responseURI="ipfs://QmResponse",
    tag="market-order",
)
resp_tx.wait_confirmed(timeout=180)

status = sdk.getValidationStatus(req.requestHash)
print(status)
```

## Search and Indexing

- `searchAgents()` / `getAgent()` are available in the SDK API.
- Current release does **not** enable subgraph URL integration by default.
- Full subgraph-backed search support is planned in a future update.

## Samples

Runnable scripts are in `python/sample/`:

- `sample/bsc_register.py`
- `sample/tron_register.py`
- `sample/bsc_reputation_flow.py`
- `sample/tron_reputation_flow.py`

Detailed sample guide: `python/sample/README.md`

## Notes

- Package name: `bankofai-8004-sdk`
- Python module path: `bankofai.sdk_8004`
- Contracts reject self-feedback; use a separate reviewer wallet

## License

MIT
