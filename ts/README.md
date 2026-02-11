# BankOfAI 8004 SDK (TypeScript)

TypeScript SDK for agent identity, discovery, trust, and reputation based on 8004.

This SDK lets you register agents on-chain, configure MCP/A2A metadata, manage agent wallets, submit/read feedback, and run validation flows on BSC and TRON.

## What Does This SDK Do?

BankOfAI 8004 SDK enables you to:

- Create and manage on-chain agent identities
- Register agent card URIs on-chain (`agent.register()`)
- Configure MCP/A2A endpoints, skills/domains, trust flags, metadata, active/x402 flags
- Manage verified wallet binding (`agent.getWallet()`, `agent.setWallet()`, `agent.unsetWallet()`)
- Submit and read feedback (`giveFeedback()`, `getFeedback()`, `getReputationSummary()`)
- Run validation request/response flows (`validationRequest()`, `validationResponse()`, `getValidationStatus()`)
- Use one SDK API across EVM (BSC) and TRON

## Network Support

- BSC Mainnet: `eip155:56`
- BSC Testnet: `eip155:97`
- TRON Mainnet: `mainnet` or `tron:mainnet`
- TRON Nile: `nile` or `tron:nile`
- TRON Shasta: `shasta` or `tron:shasta`

Package import:

```ts
import { SDK } from "@bankofai/8004-sdk";
```

## Installation

### Prerequisites

- Node.js `>=20`
- npm
- Funded private key for write operations
- RPC endpoint for target chain

### Install from Source (Local)

```bash
git clone https://github.com/bankofai/8004-sdk.git
cd 8004-sdk/ts
npm install
npm run build
```

## Quick Start

### 1. Initialize SDK

BSC Testnet:

```ts
import { SDK } from "@bankofai/8004-sdk";

const sdk = new SDK({
  network: "eip155:97",
  rpcUrl: "https://data-seed-prebsc-1-s1.binance.org:8545",
  signer: "<EVM_PRIVATE_KEY>",
});
```

TRON Nile:

```ts
import { SDK } from "@bankofai/8004-sdk";

const sdk = new SDK({
  chainId: 1,
  network: "nile",
  rpcUrl: "https://nile.trongrid.io",
  signer: "<TRON_PRIVATE_KEY>",
  feeLimit: 120_000_000,
});
```

### 2. Create and Register Agent

```ts
const agent = sdk.createAgent({
  name: "My AI Agent",
  description: "Demo agent",
  image: "https://example.com/agent.png",
});

agent.setMCP("https://mcp.example.com/");
agent.setA2A("https://a2a.example.com/.well-known/agent-card.json");
agent.addSkill("data_engineering/data_transformation_pipeline");
agent.addDomain("technology/data_science/data_science");
agent.setTrust({ reputation: true, cryptoEconomic: true });
agent.setMetadata({ version: "1.0.0", category: "demo" });
agent.setActive(true);
agent.setX402Support(true);

const tx = await agent.register("https://example.com/agent-card.json");
const mined = await tx.waitConfirmed({ timeoutMs: 180_000 });
console.log(mined.result.agentId, mined.result.agentURI);
```

### 3. Wallet Management

```ts
const wallet = await agent.getWallet();
console.log("current wallet", wallet);

const setTx = await agent.setWallet("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb");
if (setTx) await setTx.waitConfirmed({ timeoutMs: 180_000 });

const unsetTx = await agent.unsetWallet();
if (unsetTx) await unsetTx.waitConfirmed({ timeoutMs: 180_000 });
```

### 4. Feedback and Reputation

```ts
const fbTx = await sdk.giveFeedback({
  agentId: "97:1",
  value: 88,
  tag1: "execution",
  tag2: "market-swap",
  endpoint: "/a2a/x402/execute",
});
const fb = await fbTx.waitConfirmed({ timeoutMs: 180_000 });
console.log(fb.result);

const record = await sdk.getFeedback("97:1", "0xReviewerAddress", 1);
console.log(record);

const summary = await sdk.getReputationSummary("97:1");
console.log(summary);
```

### 5. Validation Flow

```ts
const reqTx = await sdk.validationRequest({
  validatorAddress: "0xValidatorAddress",
  agentId: "97:1",
  requestURI: "ipfs://QmRequest",
});
const req = await reqTx.waitConfirmed({ timeoutMs: 180_000 });

const respTx = await sdk.validationResponse({
  requestHash: req.result.requestHash,
  response: 95,
  responseURI: "ipfs://QmResponse",
  tag: "market-order",
});
await respTx.waitConfirmed({ timeoutMs: 180_000 });

const status = await sdk.getValidationStatus(req.result.requestHash);
console.log(status);
```

## Search and Indexing

- `searchAgents()` / `getAgent()` APIs exist in the SDK.
- Current release does **not** enable subgraph URL integration by default.
- Full subgraph-backed search support is planned in a future update.

## Examples

Runnable examples in `ts/examples/`:

- `examples/register-bsc.ts`
- `examples/register-tron.ts`
- `examples/wallet-smoke.ts`
- `examples/reputation-smoke.ts`
- `examples/validation-smoke.ts`

Detailed examples guide: `ts/examples/README.md`

Run examples:

```bash
npx tsx examples/register-bsc.ts
npx tsx examples/register-tron.ts
npx tsx examples/wallet-smoke.ts
npx tsx examples/reputation-smoke.ts
npx tsx examples/validation-smoke.ts
```

## Notes

- Package name: `@bankofai/8004-sdk`
- ESM package (`"type": "module"`)
- Contracts reject self-feedback; use a separate reviewer wallet

## License

MIT
