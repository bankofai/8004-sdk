# BankOfAI ERC-8004 SDK

Multi-chain SDK for ERC/TRC-8004 agent registration and reputation.

## Supports

- EVM (`web3.py`), including BSC
- TRON (`tronpy`), including Nile/Mainnet/Shasta

Entrypoint:

```python
from bankofai.erc_8004.core.sdk import SDK
```

## Install (Local)

```bash
git clone <your-repo-url>
cd tron-8004-sdk
pip install -e .
```

## Minimal Usage

### BSC Testnet

```python
from bankofai.erc_8004.core.sdk import SDK

sdk = SDK(
    chainId=97,
    rpcUrl="https://data-seed-prebsc-1-s1.binance.org:8545",
    network="evm:bsc",
    signer="<EVM_PRIVATE_KEY>",
)

agent = sdk.createAgent(name="My Agent", description="demo")
tx = agent.register("https://example.com/agent-card.json")
print(tx.wait_confirmed(timeout=180).result.agentId)
```

### TRON Nile

```python
from bankofai.erc_8004.core.sdk import SDK

sdk = SDK(
    chainId=1,
    rpcUrl="https://nile.trongrid.io",
    network="nile",
    signer="<TRON_PRIVATE_KEY>",
    feeLimit=120_000_000,
)

agent = sdk.createAgent(name="My Agent", description="demo")
tx = agent.register("https://example.com/agent-card.json")
print(tx.wait_confirmed(timeout=120).result.agentId)
```

## Samples

See runnable scripts in `sample/`:

- `sample/tron_register.py`
- `sample/bsc_register.py`
- `sample/tron_reputation_flow.py`
- `sample/bsc_reputation_flow.py`

Details: `sample/README.md`

## Notes

- Version starts at `1.0.0` in this repository.
- Search depends on subgraph URLs (`DEFAULT_SUBGRAPH_URLS` / `subgraphOverrides`).
- TRON subgraph search is not enabled in current runtime path.
- `setWallet()` is EVM-only (EIP-712 flow).
- TRON contracts reject self-feedback; use a separate reviewer wallet.

## License

MIT
