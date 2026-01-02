# trc-8004-sdk

Minimal TRC-8004 SDK implementation for local development.

## Layout
- `src/sdk/agent_sdk.py`: main `AgentSDK`
- `src/sdk/signer.py`: signer interface + simple signer
- `src/sdk/contract_adapter.py`: contract adapter interface + dummy adapter

## Usage
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

## Sample: build commitment + request hash
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

## Sample: build A2A payloads
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
