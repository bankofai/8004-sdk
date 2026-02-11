import type { AgentSummary, SearchFilters, SearchOptions } from "../models/types.js";
import { SubgraphClient } from "./subgraph-client.js";

export class AgentIndexer {
  constructor(
    private readonly defaultChainId: number,
    private readonly subgraphClients: Map<number, SubgraphClient>,
  ) {}

  private clientFor(chainId?: number): SubgraphClient | undefined {
    return this.subgraphClients.get(chainId ?? this.defaultChainId);
  }

  async searchAgents(filters: SearchFilters = {}, options: SearchOptions = {}, chainId?: number): Promise<AgentSummary[]> {
    const client = this.clientFor(chainId);
    if (!client) return [];
    return client.searchAgents(chainId ?? this.defaultChainId, filters, options);
  }

  async getAgent(agentId: string, chainId?: number): Promise<AgentSummary | undefined> {
    const resolvedChain = chainId ?? (agentId.includes(":") ? Number(agentId.split(":")[0]) : this.defaultChainId);
    const client = this.clientFor(resolvedChain);
    if (!client) return undefined;
    return client.getAgent(resolvedChain, agentId);
  }
}
