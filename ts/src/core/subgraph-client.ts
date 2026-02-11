import { GraphQLClient, gql } from "graphql-request";
import type { AgentSummary, SearchFilters, SearchOptions } from "../models/types.js";

interface RawAgent {
  id?: string;
  agentId?: string;
  name?: string;
  description?: string;
  image?: string;
  agentURI?: string;
  active?: boolean;
  x402support?: boolean;
  updatedAt?: string | number;
}

export class SubgraphClient {
  private readonly client: GraphQLClient;

  constructor(readonly url: string) {
    this.client = new GraphQLClient(url);
  }

  async searchAgents(chainId: number, filters: SearchFilters = {}, options: SearchOptions = {}): Promise<AgentSummary[]> {
    const where: Record<string, unknown> = {};
    if (typeof filters.active === "boolean") where.active = filters.active;
    if (typeof filters.x402support === "boolean") where.x402support = filters.x402support;
    if (filters.name) where.name_contains_nocase = filters.name;

    const query = gql`
      query SearchAgents($where: Agent_filter, $first: Int!, $skip: Int!, $orderBy: Agent_orderBy, $orderDirection: OrderDirection) {
        agents(where: $where, first: $first, skip: $skip, orderBy: $orderBy, orderDirection: $orderDirection) {
          id
          agentId
          name
          description
          image
          agentURI
          active
          x402support
          updatedAt
        }
      }
    `;

    try {
      const data = await this.client.request<{ agents: RawAgent[] }>(query, {
        where,
        first: options.first ?? 100,
        skip: options.skip ?? 0,
        orderBy: options.orderBy ?? "updatedAt",
        orderDirection: options.orderDirection ?? "desc",
      });

      return (data.agents || [])
        .map((x) => this.mapAgent(chainId, x))
        .filter((x) => {
          if (!filters.keyword) return true;
          const needle = filters.keyword.toLowerCase();
          return `${x.name || ""} ${x.description || ""}`.toLowerCase().includes(needle);
        });
    } catch {
      return [];
    }
  }

  async getAgent(chainId: number, agentId: string): Promise<AgentSummary | undefined> {
    const id = agentId.includes(":") ? agentId : `${chainId}:${agentId}`;

    const query = gql`
      query GetAgent($id: ID!) {
        agent(id: $id) {
          id
          agentId
          name
          description
          image
          agentURI
          active
          x402support
          updatedAt
        }
      }
    `;

    try {
      const data = await this.client.request<{ agent?: RawAgent }>(query, { id });
      if (!data.agent) return undefined;
      return this.mapAgent(chainId, data.agent);
    } catch {
      return undefined;
    }
  }

  private mapAgent(chainId: number, raw: RawAgent): AgentSummary {
    const id = String(raw.id || raw.agentId || "");
    const chainPart = id.includes(":") ? Number(id.split(":")[0]) : chainId;
    const tokenId = Number(id.includes(":") ? id.split(":")[1] : id || 0);

    return {
      id,
      agentId: id,
      chainId: chainPart,
      tokenId,
      name: raw.name,
      description: raw.description,
      image: raw.image,
      agentURI: raw.agentURI,
      active: raw.active,
      x402support: raw.x402support,
      updatedAt: raw.updatedAt === undefined ? undefined : Number(raw.updatedAt),
    };
  }
}
