# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-11

### Added
- **Core SDK**: Initial stable release of the 8004 SDK for Python and TypeScript.
- **Multi-Chain**: Support for `eip155` (EVM) and `tron` (Nile, Shasta, Mainnet) architectures.
- **Identity**: Implementation of `register`, `setWallet`, and `getAgentWallet` flows.
- **Reputation**: Added `giveFeedback`, `getFeedback`, and `getReputationSummary` with support for decimal values and dual-tagging.
- **Validation**: Introduced `validationRequest`, `validationResponse`, and `getValidationStatus` for agent-specific verification flows.
- **Discovery**: Integrated `AgentIndexer` for searching agents across supported networks.
- **Shared Resources**: Centralized `chains.json` and contract ABIs in `resource/` directory.
- **Examples**: Comprehensive smoke tests and usage samples in `ts/examples` and `python/sample`.
