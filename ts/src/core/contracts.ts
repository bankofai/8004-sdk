import contractAbisJson from "../../resource/contract_abis.json" with { type: "json" };

export const CONTRACT_ABIS = contractAbisJson as Record<string, { abi: Record<string, unknown[]> }>;

export function getIdentityRegistryAbi(chainType: "evm" | "tron"): unknown[] {
  if (chainType === "evm") return CONTRACT_ABIS.bsc.abi.identityRegistry;
  return CONTRACT_ABIS.tron.abi.identityRegistry;
}

export function getReputationRegistryAbi(chainType: "evm" | "tron"): unknown[] {
  if (chainType === "evm") return CONTRACT_ABIS.bsc.abi.reputationRegistry;
  return CONTRACT_ABIS.tron.abi.reputationRegistry;
}

export function getValidationRegistryAbi(chainType: "evm" | "tron"): unknown[] {
  if (chainType === "evm") return CONTRACT_ABIS.bsc.abi.validationRegistry;
  return CONTRACT_ABIS.tron.abi.validationRegistry;
}
