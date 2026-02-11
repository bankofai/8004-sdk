import { SDK } from "../src/index.js";

const PRIVATE_KEY = "<EVM_PRIVATE_KEY>";

const sdk = new SDK({
  network: "eip155:97",
  rpcUrl: "https://data-seed-prebsc-1-s1.binance.org:8545",
  signer: PRIVATE_KEY,
});

const agent = sdk.createAgent({
  name: `TS BSC Agent ${Date.now()}`,
  description: "TypeScript register sample on BSC testnet",
  image: "https://example.com/agent.png",
});

agent.setMCP("https://mcp.example.com/");
agent.setA2A("https://a2a.example.com/.well-known/agent-card.json");
agent.setTrust({ reputation: true, cryptoEconomic: true });
agent.setMetadata({ version: "1.0.0", runtime: "ts" });
agent.setX402Support(true);

const tx = await agent.register("https://example.com/agent-card.json");
console.log("tx:", tx.txHash);
const mined = await tx.waitConfirmed({ timeoutMs: 180_000 });
console.log("agent:", mined.result.agentId);
