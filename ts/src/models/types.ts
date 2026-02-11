export type ChainType = "evm" | "tron";

export interface SDKConfig {
  chainId?: number;
  rpcUrl?: string;
  network: string;
  signer?: string;
  feeLimit?: number;
  subgraphUrl?: string;
  subgraphOverrides?: Record<number, string>;
}

export interface RegistrationResult {
  agentId?: string;
  agentURI: string;
}

export interface SetWalletOptions {
  newWalletSigner?: string;
  deadline?: number;
  signature?: `0x${string}`;
}

export interface GiveFeedbackParams {
  agentId: string | number;
  value: number;
  reviewerSigner?: string;
  tag1?: string;
  tag2?: string;
  endpoint?: string;
  feedbackURI?: string;
  feedbackHash?: `0x${string}`;
}

export interface FeedbackRecord {
  agentId: string;
  reviewer: string;
  feedbackIndex: number;
  value: number;
  valueDecimals: number;
  tag1: string;
  tag2: string;
  isRevoked: boolean;
}

export interface ReputationSummary {
  agentId: string;
  count: number;
  summaryValue: number;
  summaryValueDecimals: number;
  averageValue: number;
}

export interface ValidationRequestParams {
  validatorAddress: string;
  agentId: string | number;
  requestURI: string;
  requestHash?: `0x${string}`;
}

export interface ValidationResponseParams {
  requestHash: `0x${string}`;
  response: number;
  responseURI?: string;
  responseHash?: `0x${string}`;
  tag?: string;
}

export interface ValidationStatus {
  validatorAddress: string;
  agentId: string;
  response: number;
  responseHash: `0x${string}`;
  tag: string;
  lastUpdate: number;
}

export interface TxWaitOptions {
  timeoutMs?: number;
  pollMs?: number;
  throwOnRevert?: boolean;
}

export interface TxMined<T> {
  receipt: unknown;
  result: T;
}

export interface RegistrationFile {
  agentId?: string;
  agentURI?: string;
  walletAddress?: string;
  walletChainId?: number;
  name: string;
  description: string;
  image?: string;
  endpoints: Array<{ name: string; endpoint: string; version?: string }>;
  tags: string[];
  metadata: Record<string, unknown>;
  supportedTrust: string[];
  active: boolean;
  x402support: boolean;
  updatedAt: number;
}

export interface ChainContracts {
  identityRegistry: string;
  reputationRegistry: string;
  validationRegistry: string;
}

export interface AgentSummary {
  id: string;
  agentId: string;
  chainId: number;
  tokenId: number;
  name?: string;
  description?: string;
  image?: string;
  agentURI?: string;
  active?: boolean;
  x402support?: boolean;
  updatedAt?: number;
}

export interface SearchFilters {
  name?: string;
  active?: boolean;
  x402support?: boolean;
  keyword?: string;
}

export interface SearchOptions {
  first?: number;
  skip?: number;
  orderBy?: "updatedAt" | "createdAt" | "name";
  orderDirection?: "asc" | "desc";
}
