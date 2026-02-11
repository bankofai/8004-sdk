# BankOfAI 8004 SDK (TypeScript)

TypeScript SDK for agent identity, discovery, trust, and reputation based on 8004.

This SDK provides a unified API for registration, wallet binding, feedback/reputation, and validation workflows.

## What Does This SDK Do?

BankOfAI 8004 SDK enables you to:

- Create and manage on-chain agent identities
- Register agent card URIs on-chain (`agent.register()`)
- Configure MCP/A2A endpoints, skills/domains, trust flags, metadata, and status
- Manage verified wallet binding (`agent.getWallet()`, `agent.setWallet()`, `agent.unsetWallet()`)
- Submit and read feedback (`giveFeedback()`, `getFeedback()`, `getReputationSummary()`)
- Run validation request/response flows (`validationRequest()`, `validationResponse()`, `getValidationStatus()`)

Package import:

```ts
import { SDK } from "@bankofai/8004-sdk";
```

## Installation

### Prerequisites

- Node.js `>=20`
- npm
- Funded private key for write operations
- RPC endpoint

### Install from Source (Local)

```bash
git clone https://github.com/bankofai/8004-sdk.git
cd 8004-sdk/ts
npm install
npm run build
```

## Quick Start

```ts
import { SDK } from "@bankofai/8004-sdk";

const sdk = new SDK({
  network: "<NETWORK_ID>", // e.g. eip155:97 or nile
  rpcUrl: "<RPC_URL>",
  signer: "<PRIVATE_KEY>",
});

const agent = sdk.createAgent({
  name: "My AI Agent",
  description: "Demo agent",
  image: "https://example.com/agent.png",
});

agent.setMCP("https://mcp.example.com/");
agent.setA2A("https://a2a.example.com/.well-known/agent-card.json");
agent.setTrust({ reputation: true, cryptoEconomic: true });
agent.setMetadata({ version: "1.0.0" });
agent.setActive(true);

const tx = await agent.register("https://example.com/agent-card.json");
const mined = await tx.waitConfirmed({ timeoutMs: 180_000 });
console.log(mined.result.agentId, mined.result.agentURI);
```

## Core Flows

### Wallet Management

```ts
const wallet = await agent.getWallet();
const setTx = await agent.setWallet("<NEW_WALLET_ADDRESS>");
if (setTx) await setTx.waitConfirmed({ timeoutMs: 180_000 });
```

### Feedback and Reputation

```ts
const fbTx = await sdk.giveFeedback({ agentId: "<AGENT_ID>", value: 88 });
const fb = await fbTx.waitConfirmed({ timeoutMs: 180_000 });
const summary = await sdk.getReputationSummary("<AGENT_ID>");
console.log(fb.result, summary);
```

### Validation

```ts
const reqTx = await sdk.validationRequest({
  validatorAddress: "<VALIDATOR_ADDRESS>",
  agentId: "<AGENT_ID>",
  requestURI: "ipfs://QmRequest",
});
const req = await reqTx.waitConfirmed({ timeoutMs: 180_000 });

const respTx = await sdk.validationResponse({
  requestHash: req.result.requestHash,
  response: 95,
});
await respTx.waitConfirmed({ timeoutMs: 180_000 });
```

## Search and Indexing

- `searchAgents()` / `getAgent()` APIs exist in the SDK.
- Current release does **not** enable subgraph URL integration by default.
- Full subgraph-backed search support is planned in a future update.

## Examples

Chain-specific runnable scripts are in `ts/examples/`.
See `ts/examples/README.md` for full usage.

## Notes

- Package name: `@bankofai/8004-sdk`
- ESM package (`"type": "module"`)
- Contracts reject self-feedback; use a separate reviewer wallet

## License

MIT
