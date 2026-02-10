# tron-8004-sdk

This project is a Python SDK for ERC/TRC‑8004 style agent registration, discovery, and reputation.

It provides:
- On-chain agent registration and metadata management (IdentityRegistry)
- Reputation feedback submission (ReputationRegistry)
- Optional validation request/response flows (ValidationRegistry)
- Agent registration file helpers and OASF taxonomy support

EVM-compatible chains are supported via `web3.py` (e.g. Ethereum, Base, BSC).  
TRON-specific support depends on the separate TRON adapter implementation.

Notes:
- If no subgraph URL is configured, search/index features are limited, but on-chain actions still work.
- BSC Mainnet/Testnet contract addresses are configured in `src/sdk/core/contracts.py`.
