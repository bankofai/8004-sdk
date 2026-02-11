# Release v1.0.0

This is the initial stable release of the **BankOfAI 8004 SDK**, providing a unified development interface for decentralized AI agent identity, reputation, and validation across EVM and Tron networks.

## 🚀 Key Features

### 🌐 Multi-Chain Support
- Full compatibility with **EVM** (e.g., BSC, Base) and **Tron** (Mainnet, Nile, Shasta).
- Unified chain resolution and contract address management via `chains.json`.

### 🆔 Agent Identity (ERC/TRC-8004)
- **Registration**: Easily register agent cards with IPFS or HTTP URIs.
- **Wallet Binding**: Securely link verified wallets to agent identities on-chain.
- **Metadata**: Manage custom agent attributes, endpoints (MCP/A2A), and skills.

### ⭐ Reputation & Trust
- **Feedback Flow**: Submit and retrieve agent feedback with high-precision decimal values.
- **Tagging**: Categorize reputation using dual tags (`tag1`, `tag2`) for granular filtering.
- **Aggregated Summaries**: Fetch real-time average ratings and feedback counts.

### ✅ Validation Framework
- **Request/Response**: Standardized on-chain flow for users to request behavioral validation from agents.
- **Proof of Action**: Securely track and verify agent responses.

### 🔍 Discovery & Search
- **Agent Indexer**: Efficiently search for agents by name, description, tools, or status.
- **Parity**: Seamless experience across **TypeScript** and **Python** SDKs.

## 📦 Installation

### TypeScript
```bash
npm install @bankofai/8004-sdk
```

### Python
```bash
pip install bankofai-8004-sdk
```

## 🛠 Developer Resources
- **Guidelines**: Check [AGENTS.md](AGENTS.md) for coding standards and synchronization rules.
- **Examples**: 
  - TS: `ts/examples/`
  - Python: `python/sample/`

---
**Full Changelog**: https://github.com/bankofai/8004-sdk/commits/v1.0.0
