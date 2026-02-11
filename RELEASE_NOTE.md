# Release v1.1.0

The **BankOfAI 8004 SDK v1.1.0** introduces significant enhancements to agent lifecycle management, reputation interactions, and discovery features across both TypeScript and Python platforms.

## 🚀 What's New

### 🛠 Enhanced Agent Lifecycle
- **Ownership & Control**: New `transfer()`, `addOperator()`, and `removeOperator()` methods provide granular control over agent identities.
- **Data Persistence**: `loadAgent()` allows developers to fully hydrate agent objects from a mix of on-chain metadata and off-chain (IPFS/HTTP) agent cards.
- **Updates**: Support for updating agent registration URIs and on-chain metadata keys post-registration.

### ⭐ Advanced Reputation Features
- **Two-Way Feedback**: Agents can now respond to user feedback using the `appendResponse()` flow.
- **Feedback Management**: Reviewers can retract their feedback using `revokeFeedback()`.
- **Granular Search**: The new `searchFeedback()` API supports filtering by tags, value ranges, reviewer addresses, and specific agent capabilities/skills.

### 📦 IPFS Integration
- Native support for IPFS-based registration flows.
- Customizable `ipfsUploader` hook for integrating with any pinning service.
- Automatic CID-to-Gateway resolution for fetching agent cards.

### 🐍 Python & TypeScript Parity
- Full feature parity maintained between both SDKs.
- Unified naming conventions and consistent error handling.

## 📦 Installation

### TypeScript
```bash
npm install @bankofai/8004-sdk@1.1.0
```

### Python
```bash
pip install bankofai-8004-sdk==1.1.0
```

## 🛠 Developer Resources
- **Updated Examples**: Check out the new response and transfer samples in `ts/examples/` and `python/sample/`.
- **Guidelines**: Refer to [AGENTS.md](AGENTS.md) for the latest synchronization standards.

---
**Full Changelog**: https://github.com/bankofai/8004-sdk/compare/v1.0.0...v1.1.0
