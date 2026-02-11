# BankOfAI 8004 SDK (TypeScript)

TypeScript SDK for ERC/TRC-8004 with dual-chain support:
- BSC (EVM)
- TRON (Nile/Mainnet/Shasta)

This package is currently for local development in this monorepo.

## Install (Local)

```bash
cd 8004-sdk/ts
npm install
npm run build
```

## Usage

```ts
import { SDK } from "@bankofai/8004-sdk";

const sdk = new SDK({
  chainId: 97,
  network: "evm:bsc",
  rpcUrl: "https://data-seed-prebsc-1-s1.binance.org:8545",
  signer: "<EVM_PRIVATE_KEY>",
});

const agent = sdk.createAgent({
  name: "My Agent",
  description: "demo",
});

const tx = await agent.register("https://example.com/agent-card.json");
const mined = await tx.waitConfirmed({ timeoutMs: 180_000 });
console.log(mined.result.agentId);
```

TRON usage is the same pattern:

```ts
const sdk = new SDK({
  chainId: 1,
  network: "nile",
  rpcUrl: "https://nile.trongrid.io",
  signer: "<TRON_PRIVATE_KEY>",
  feeLimit: 120_000_000,
});
```

## Features (MVP)

- Network/config resolution from `resource/chains.json`
- ABI loading from `resource/contract_abis.json`
- `SDK` + `Agent` API
- `createAgent()`
- `agent.register()`
- `agent.getWallet()`
- `agent.setWallet()` (EIP-712 typed-data signature path for EVM and TRON)
- `agent.unsetWallet()`
- `sdk.giveFeedback()` / `sdk.getFeedback()` / `sdk.getReputationSummary()`
- `sdk.validationRequest()` / `sdk.validationResponse()` / `sdk.getValidationStatus()`
- `sdk.searchAgents()` / `sdk.getAgent()` API placeholders
- Cross-chain adapters (Viem for EVM, TronWeb for TRON)

Notes:
- Contracts reject self-feedback. Use `reviewerSigner` in `giveFeedback()` with a separate funded wallet.
- `subgraph URL` is not supported in the current release.
- Subgraph-based search will be supported in a future update.

## Examples

- `examples/register-bsc.ts`
- `examples/register-tron.ts`
- `examples/wallet-smoke.ts`
- `examples/reputation-smoke.ts`
- `examples/validation-smoke.ts`

Detailed guide: `examples/README.md`

Run examples:

```bash
npx tsx examples/register-bsc.ts
npx tsx examples/register-tron.ts
npx tsx examples/wallet-smoke.ts
npx tsx examples/reputation-smoke.ts
npx tsx examples/validation-smoke.ts
```

## Notes

- This is an MVP scaffold aligned to the current Python SDK architecture.
- Advanced methods (reputation/search/validation helpers/full parity with python) are planned next.
