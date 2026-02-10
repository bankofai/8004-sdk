# tron-8004-sdk

Python SDK for ERC/TRC-8004 agent registration, discovery, and reputation.

## What It Does
- Register and update agents on-chain (`IdentityRegistry`)
- Submit and read reputation feedback (`ReputationRegistry`)
- Manage registration metadata/endpoints/OASF fields
- Search/index agents (subgraph-dependent)

## Chain Support
- EVM chains via `web3.py` (Ethereum/Base/BSC)
- TRON chains via `tronpy` (Mainnet/Nile/Shasta)
- One unified SDK entrypoint: `bankofai.erc_8004.core.sdk.SDK`

## Quick Start
```python
from bankofai.erc_8004.core.sdk import SDK

# TRON Nile
tron_sdk = SDK(
    chainId=1,
    rpcUrl="https://nile.trongrid.io",
    network="nile",  # also supports "tron:nile"
    signer="<PRIVATE_KEY>",
    feeLimit=120_000_000,
)

# BSC Testnet
bsc_sdk = SDK(
    chainId=97,
    rpcUrl="https://data-seed-prebsc-1-s1.binance.org:8545",
    network="evm:bsc",
    signer="<PRIVATE_KEY>",
)
```

## Config Files
- Network/address config: `resource/chains.json`
- ABI records: `resource/contract_abis.json`
- Runtime default registries and built-in ABI: `src/bankofai/erc_8004/core/contracts.py`

## Notes
- If no subgraph URL is configured, search/index features are limited, but on-chain actions still work.
- `setWallet()` currently supports EVM only (EIP-712 flow).
