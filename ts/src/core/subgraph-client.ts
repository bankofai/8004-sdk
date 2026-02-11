import { GraphQLClient, gql } from "graphql-request";
import type {
  AgentSummary,
  FeedbackSearchFilters,
  FeedbackSearchOptions,
  FeedbackSummary,
  SearchFilters,
  SearchOptions,
} from "../models/types.js";

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

interface RawFeedback {
  id?: string;
  clientAddress?: string;
  feedbackIndex?: string | number;
  value?: string | number;
  valueDecimals?: string | number;
  tag1?: string;
  tag2?: string;
  endpoint?: string;
  isRevoked?: boolean;
  createdAt?: string | number;
  agent?: { id?: string; agentId?: string };
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

  async searchFeedback(
    chainId: number,
    filters: FeedbackSearchFilters = {},
    options: FeedbackSearchOptions = {},
  ): Promise<FeedbackSummary[]> {
    const where: Record<string, unknown> = {};
    const agents = [...(filters.agents ?? []), ...(filters.agentId ? [filters.agentId] : [])];
    if (agents.length > 0) where.agent_in = agents;
    if (filters.reviewers && filters.reviewers.length > 0) where.clientAddress_in = filters.reviewers;
    if (!filters.includeRevoked) where.isRevoked = false;

    const query = gql`
      query SearchFeedback(
        $where: Feedback_filter
        $first: Int!
        $skip: Int!
        $orderBy: Feedback_orderBy
        $orderDirection: OrderDirection
      ) {
        feedbacks(where: $where, first: $first, skip: $skip, orderBy: $orderBy, orderDirection: $orderDirection) {
          id
          clientAddress
          feedbackIndex
          value
          valueDecimals
          tag1
          tag2
          endpoint
          isRevoked
          createdAt
          agent { id agentId }
        }
      }
    `;

    try {
      const data = await this.client.request<{ feedbacks: RawFeedback[] }>(query, {
        where,
        first: options.first ?? 100,
        skip: options.skip ?? 0,
        orderBy: options.orderBy ?? "createdAt",
        orderDirection: options.orderDirection ?? "desc",
      });

      return (data.feedbacks ?? [])
        .map((x) => this.mapFeedback(chainId, x))
        .filter((x) => {
          if (filters.tags && filters.tags.length > 0) {
            const set = new Set(filters.tags.map((t) => t.toLowerCase()));
            const tag1 = (x.tag1 || "").toLowerCase();
            const tag2 = (x.tag2 || "").toLowerCase();
            if (!set.has(tag1) && !set.has(tag2)) return false;
          }
          if (!filters.keyword) return true;
          const needle = filters.keyword.toLowerCase();
          const hay = [
            x.tag1 || "",
            x.tag2 || "",
            x.endpoint || "",
          ].join(" ").toLowerCase();
          return hay.includes(needle);
        })
        .filter((x) => (filters.minValue === undefined ? true : x.value >= filters.minValue))
        .filter((x) => (filters.maxValue === undefined ? true : x.value <= filters.maxValue))
        .filter((x) => {
          if (!filters.names || filters.names.length === 0) return true;
          const names = new Set(filters.names.map((n) => n.toLowerCase()));
          return names.has((x.tag1 || "").toLowerCase()) || names.has((x.tag2 || "").toLowerCase());
        })
        .filter((x) => {
          if (!filters.skills || filters.skills.length === 0) return true;
          const skills = new Set(filters.skills.map((n) => n.toLowerCase()));
          const text = `${x.tag1 || ""} ${x.tag2 || ""} ${x.endpoint || ""}`.toLowerCase();
          return [...skills].some((s) => text.includes(s));
        })
        .filter((x) => {
          if (!filters.tasks || filters.tasks.length === 0) return true;
          const tasks = new Set(filters.tasks.map((n) => n.toLowerCase()));
          const text = `${x.tag1 || ""} ${x.tag2 || ""} ${x.endpoint || ""}`.toLowerCase();
          return [...tasks].some((s) => text.includes(s));
        })
        .filter((x) => {
          if (!filters.capabilities || filters.capabilities.length === 0) return true;
          const caps = new Set(filters.capabilities.map((n) => n.toLowerCase()));
          const text = `${x.tag1 || ""} ${x.tag2 || ""} ${x.endpoint || ""}`.toLowerCase();
          return [...caps].some((s) => text.includes(s));
        });
    } catch {
      return [];
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

  private mapFeedback(chainId: number, raw: RawFeedback): FeedbackSummary {
    const fallbackId = String(raw.id || "");
    const agentRaw = String(raw.agent?.id || raw.agent?.agentId || "");
    const agentId = agentRaw || (fallbackId.includes(":") ? fallbackId.split(":").slice(0, 2).join(":") : `${chainId}:0`);
    const reviewer = String(raw.clientAddress || "");
    const feedbackIndex =
      raw.feedbackIndex === undefined ? 0 : Number(raw.feedbackIndex);
    const valueDecimals = raw.valueDecimals === undefined ? 0 : Number(raw.valueDecimals);
    const valueRaw = raw.value === undefined ? 0 : Number(raw.value);
    const divisor = 10 ** valueDecimals;

    return {
      id: fallbackId,
      agentId,
      reviewer,
      feedbackIndex,
      value: divisor === 0 ? valueRaw : valueRaw / divisor,
      valueDecimals,
      tag1: raw.tag1 || "",
      tag2: raw.tag2 || "",
      endpoint: raw.endpoint || "",
      isRevoked: Boolean(raw.isRevoked),
      createdAt: raw.createdAt === undefined ? undefined : Number(raw.createdAt),
    };
  }
}
