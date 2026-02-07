# TRON-8004 Agent SDK

Python SDK for decentralized Agent collaboration, implementing the ERC-8004 (Trustless Agent Protocol) specification.

## Features

- 🔗 **Multi-chain Support**: Abstract Adapter architecture, currently supporting TRON, extendable to EVM chains.
- 🔄 **Automatic Retry**: Configurable exponential backoff retry strategy.
- 🛡️ **Type Safety**: Complete type annotations and Pydantic validation.
- 📝 **Detailed Logging**: Structured logging for easy debugging.
- ⚡ **Async Support**: Provides both synchronous and asynchronous APIs.

## Installation

```bash
# Using uv
uv add tron-8004-sdk

# Using pip
pip install tron-8004-sdk
```

## CLI Tool

After installation, you can use the `tron8004` command-line tool:

```bash
# Create a new Agent project
tron8004 init MyAgent
tron8004 init MyAgent --port 8200 --tags "swap,defi"

# Test Agent connectivity
tron8004 test --url http://localhost:8100

# Register Agent on-chain
tron8004 register --token-uri https://example.com/agent.json --name MyAgent
```

### Create Agent Project Example

```bash
$ tron8004 init MySwapAgent --port 8200 --tags "swap,defi"

✅ Agent project created successfully!

📁 myswapagent/
   ├── app.py           # Agent main program
   ├── pyproject.toml   # Project configuration
   ├── .env.example     # Environment variable template
   ├── README.md        # Documentation
   └── tests/           # Tests

🚀 Next steps:
   cd myswapagent
   uv sync
   python app.py
```

## Quick Start

```python
from sdk import AgentSDK

# Initialize SDK
sdk = AgentSDK(
    private_key="your_hex_private_key",
    rpc_url="https://nile.trongrid.io",
    network="tron:nile",
    identity_registry="TIdentityRegistryAddress",
    validation_registry="TValidationRegistryAddress",
    reputation_registry="TReputationRegistryAddress",
)

# Register Agent
tx_id = sdk.register_agent(
    token_uri="https://example.com/agent.json",
    metadata=[{"key": "name", "value": "MyAgent"}],
)
print(f"Agent registered: {tx_id}")

# Build Order Commitment
commitment = sdk.build_commitment({
    "asset": "TRX/USDT",
    "amount": 100.0,
    "slippage": 0.01,
})
```

## Core Functions

### 1. Identity Registration (IdentityRegistry)

```python
# Method 1: Register using token_uri
tx_id = sdk.register_agent(
    token_uri="https://example.com/agent.json",
    metadata=[
        {"key": "name", "value": "MyAgent"},
        {"key": "version", "value": "1.0.0"},
    ],
)

# Method 2: Automatically extract metadata from agent-card.json
import json
with open(".well-known/agent-card.json") as f:
    card = json.load(f)

metadata = AgentSDK.extract_metadata_from_card(card)
# metadata includes: name, description, version, url, skills, tags, endpoints
tx_id = sdk.register_agent(metadata=metadata)

# Update Metadata
tx_id = sdk.update_metadata(
    agent_id=1,
    key="description",
    value="Updated description",
)
```

### 2. Validation Request (ValidationRegistry)

```python
# Initiate Validation Request
tx_id = sdk.validation_request(
    validator_addr="TValidatorAddress",
    agent_id=1,
    request_uri="ipfs://QmXxx...",
    request_hash="0x" + "aa" * 32,
)

# Submit Validation Response (Called by Validator)
tx_id = sdk.validation_response(
    request_hash="0x" + "aa" * 32,
    response=95,  # 0-100 Score
    response_uri="ipfs://QmYyy...",
)
```

### 3. Reputation Feedback (ReputationRegistry)

```python
# Submit Reputation Feedback
tx_id = sdk.submit_reputation(
    agent_id=1,
    score=95,
    tag1="0x" + "11" * 32,  # Optional Tag
    feedback_auth="0x...",   # Feedback Authorization Signature provided by Agent
)
```

### 4. Signature Construction

```python
# Build A2A Request Signature
signature = sdk.build_a2a_signature(
    action_commitment="0x...",
    timestamp=int(time.time()),
    caller_address="TCallerAddress",
)

# Build Feedback Authorization
feedback_auth = sdk.build_feedback_auth(
    agent_id=1,
    client_addr="TClientAddress",
    index_limit=10,
    expiry=int(time.time()) + 3600,
    chain_id=None,  # Automatically resolved
    identity_registry="TIdentityRegistry",
)
```

### 5. Request Construction Helpers

```python
# Market Order Quote Request
quote_req = sdk.build_market_order_quote_request(
    asset="TRX/USDT",
    amount=100.0,
    slippage=0.01,
)

# X402 Execution Request
execute_req = sdk.build_x402_execute_request(
    action_commitment="0x...",
    order_params={"asset": "TRX/USDT", "amount": 100.0},
    payment_tx_hash="0x...",
    timestamp=int(time.time()),
    caller_address="TCallerAddress",
)
```

## Retry Configuration

The SDK provides a configurable retry strategy:

```python
from sdk import AgentSDK, RetryConfig, AGGRESSIVE_RETRY_CONFIG

# Use predefined configuration
sdk = AgentSDK(
    private_key="...",
    retry_config=AGGRESSIVE_RETRY_CONFIG,  # 5 retries
)

# Custom configuration
custom_config = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
)
sdk = AgentSDK(private_key="...", retry_config=custom_config)
```

Predefined configurations:
- `DEFAULT_RETRY_CONFIG`: 3 retries, 1s base delay
- `AGGRESSIVE_RETRY_CONFIG`: 5 retries, 0.5s base delay
- `CONSERVATIVE_RETRY_CONFIG`: 2 retries, 2s base delay
- `NO_RETRY_CONFIG`: No retry

## Error Handling

The SDK provides fine-grained exception types:

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
    print("Insufficient energy, please charge")
except RetryExhaustedError as e:
    print(f"Retries exhausted: {e.last_error}")
except ContractCallError as e:
    print(f"Contract call failed: {e.code} - {e.details}")
except SDKError as e:
    print(f"SDK Error: {e}")
```

Exception Hierarchy:
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

## HTTP Client

### AgentClient

Smart HTTP Client, automatically resolves endpoints from Agent metadata:

```python
from sdk import AgentClient

client = AgentClient(
    metadata=agent_metadata,  # Retrieved from Central Service
    base_url="https://agent.example.com",
)

# Automatically resolve endpoint and send request
response = client.post("quote", {"asset": "TRX/USDT", "amount": 100})
```

### AgentProtocolClient

Agent Protocol Standard Client:

```python
from sdk import AgentProtocolClient

client = AgentProtocolClient(base_url="https://agent.example.com")

# Create task and execute
result = client.run({
    "skill": "market_order",
    "params": {"asset": "TRX/USDT", "amount": 100},
})
```

## Chain Tools

```python
from sdk import load_request_data, fetch_event_logs

# Load request data (Supports file://, ipfs://, http://)
data = load_request_data("ipfs://QmXxx...")

# Fetch on-chain events
events = fetch_event_logs(
    client=tron_client,
    contract_address="TValidationRegistry",
    event_name="ValidationRequest",
    from_block=1000000,
    to_block=1001000,
)
```

## Extending Multi-chain Support

The SDK uses the Adapter pattern, making it easy to extend to other chains:

```python
from sdk import ContractAdapter, Signer

class EVMContractAdapter(ContractAdapter):
    def __init__(self, rpc_url: str, ...):
        from web3 import Web3
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
    
    def send(self, contract: str, method: str, params: list, signer: Signer) -> str:
        # EVM transaction logic
        ...

class EVMSigner(Signer):
    def __init__(self, private_key: str):
        from eth_account import Account
        self.account = Account.from_key(private_key)
    
    def sign_message(self, payload: bytes) -> str:
        # EIP-191 signature
        ...
```

## Environment Variables

| Variable | Description | Default Value |
|------|------|--------|
| `TRON_RPC_URL` | TRON RPC Node | `https://nile.trongrid.io` |
| `TRON_NETWORK` | Network Identifier | `tron:nile` |
| `IDENTITY_REGISTRY` | IdentityRegistry Address | - |
| `VALIDATION_REGISTRY` | ValidationRegistry Address | - |
| `REPUTATION_REGISTRY` | ReputationRegistry Address | - |
| `TRON_FEE_LIMIT` | Transaction Fee Limit (sun) | `10000000` |
| `IPFS_GATEWAY_URL` | IPFS Gateway | `https://ipfs.io/ipfs` |

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Type check
uv run mypy src/sdk
```

## License

MIT
