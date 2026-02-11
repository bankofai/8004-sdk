import { recoverTypedDataAddress, type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";

import type { RegistrationFile, RegistrationResult, SetWalletOptions } from "../models/types.js";
import type { SDK } from "./sdk.js";
import { TransactionHandle } from "./transaction-handle.js";

export class Agent {
  constructor(private readonly sdk: SDK, private readonly registrationFile: RegistrationFile) {}

  get agentId(): string | undefined {
    return this.registrationFile.agentId;
  }

  setMCP(endpoint: string, version = "2025-06-18"): this {
    this.registrationFile.endpoints = this.registrationFile.endpoints.filter((e) => e.name !== "MCP");
    this.registrationFile.endpoints.push({ name: "MCP", endpoint, version });
    return this.touch();
  }

  setA2A(endpoint: string, version = "0.3.0"): this {
    this.registrationFile.endpoints = this.registrationFile.endpoints.filter((e) => e.name !== "A2A");
    this.registrationFile.endpoints.push({ name: "A2A", endpoint, version });
    return this.touch();
  }

  addSkill(skill: string): this {
    if (!this.registrationFile.tags.includes(skill)) this.registrationFile.tags.push(skill);
    return this.touch();
  }

  addDomain(domain: string): this {
    if (!this.registrationFile.tags.includes(domain)) this.registrationFile.tags.push(domain);
    return this.touch();
  }

  setTrust(input: { reputation?: boolean; cryptoEconomic?: boolean; teeAttestation?: boolean }): this {
    const trust: string[] = [];
    if (input.reputation) trust.push("reputation");
    if (input.cryptoEconomic) trust.push("crypto-economic");
    if (input.teeAttestation) trust.push("tee-attestation");
    this.registrationFile.supportedTrust = trust;
    return this.touch();
  }

  setMetadata(kv: Record<string, unknown>): this {
    this.registrationFile.metadata = { ...this.registrationFile.metadata, ...kv };
    return this.touch();
  }

  setActive(active: boolean): this {
    this.registrationFile.active = active;
    return this.touch();
  }

  setX402Support(enabled: boolean): this {
    this.registrationFile.x402support = enabled;
    return this.touch();
  }

  async register(agentURI: string): Promise<TransactionHandle<RegistrationResult>> {
    const tx = await this.sdk.submitRegister(agentURI);

    return new TransactionHandle<RegistrationResult>(tx.txHash, this.sdk.chain, async (receipt) => {
      const parsed = this.sdk.chain.parseRegisteredAgentId(receipt);
      const resolved: RegistrationResult = {
        agentURI,
        agentId: parsed ? `${this.sdk.chainId}:${parsed}` : undefined,
      };
      this.registrationFile.agentURI = agentURI;
      this.registrationFile.agentId = resolved.agentId;
      this.touch();
      return resolved;
    });
  }

  async getWallet(): Promise<string | undefined> {
    if (!this.registrationFile.agentId) throw new Error("Agent must be registered first");
    return this.sdk.getAgentWallet(this.registrationFile.agentId);
  }

  async setWallet(newWallet: string, options: SetWalletOptions = {}): Promise<TransactionHandle<Agent> | undefined> {
    if (!this.registrationFile.agentId) throw new Error("Agent must be registered first");

    const agentTokenId = BigInt(this.registrationFile.agentId.split(":").pop() as string);
    const addrEvm = this.sdk.chain.toEvmAddress(newWallet);
    const addrChain = this.sdk.chain.toChainAddress(newWallet);

    const currentWallet = await this.getWallet().catch(() => undefined);
    if (currentWallet && this.sdk.chain.addressEqual(currentWallet, addrChain)) {
      this.registrationFile.walletAddress = addrChain;
      this.registrationFile.walletChainId = this.sdk.chainId;
      this.touch();
      return undefined;
    }

    const ownerChain = await this.sdk.chain.ownerOf(this.sdk.identityRegistry, this.sdk.identityRegistryAbi, agentTokenId);
    const ownerEvm = this.sdk.chain.toEvmAddress(ownerChain) as Hex;
    const verifyingContract = this.sdk.chain.toEvmAddress(this.sdk.identityRegistry) as Hex;
    const chainId = this.sdk.getTypedDataChainId();
    const deadline = BigInt(options.deadline ?? (Math.floor(Date.now() / 1000) + 60));

    const domain = {
      name: "ERC8004IdentityRegistry",
      version: "1",
      chainId,
      verifyingContract,
    } as const;
    const types = {
      AgentWalletSet: [
        { name: "agentId", type: "uint256" },
        { name: "newWallet", type: "address" },
        { name: "owner", type: "address" },
        { name: "deadline", type: "uint256" },
      ],
    } as const;
    const message = {
      agentId: agentTokenId,
      newWallet: addrEvm as Hex,
      owner: ownerEvm,
      deadline,
    } as const;

    let signature = options.signature;
    if (!signature) {
      const signerKey = ((options.newWalletSigner ?? this.sdk.signer) || "").trim();
      if (!signerKey) {
        throw new Error("New wallet signature is required. Provide options.newWalletSigner or options.signature.");
      }
      const normalizedKey = (signerKey.startsWith("0x") ? signerKey : `0x${signerKey}`) as Hex;
      const account = privateKeyToAccount(normalizedKey);
      if (account.address.toLowerCase() !== addrEvm.toLowerCase()) {
        throw new Error(`newWalletSigner address (${account.address}) does not match newWallet (${addrEvm}).`);
      }
      signature = await account.signTypedData({
        domain,
        types,
        primaryType: "AgentWalletSet",
        message,
      });

      const recovered = await recoverTypedDataAddress({
        domain,
        types,
        primaryType: "AgentWalletSet",
        message,
        signature,
      });
      if (recovered.toLowerCase() !== addrEvm.toLowerCase()) {
        throw new Error(`Signature verification failed: recovered ${recovered}, expected ${addrEvm}`);
      }
    }

    const txHash = await this.sdk.chain.setAgentWallet(
      this.sdk.identityRegistry,
      this.sdk.identityRegistryAbi,
      agentTokenId,
      addrChain,
      deadline,
      signature,
    );

    return new TransactionHandle<Agent>(txHash, this.sdk.chain, async () => {
      this.registrationFile.walletAddress = addrChain;
      this.registrationFile.walletChainId = this.sdk.chainId;
      this.touch();
      return this;
    });
  }

  async unsetWallet(): Promise<TransactionHandle<Agent> | undefined> {
    if (!this.registrationFile.agentId) throw new Error("Agent must be registered first");
    const agentTokenId = BigInt(this.registrationFile.agentId.split(":").pop() as string);

    const currentWallet = await this.getWallet().catch(() => undefined);
    if (!currentWallet) {
      this.registrationFile.walletAddress = undefined;
      this.registrationFile.walletChainId = undefined;
      this.touch();
      return undefined;
    }

    const txHash = await this.sdk.chain.unsetAgentWallet(
      this.sdk.identityRegistry,
      this.sdk.identityRegistryAbi,
      agentTokenId,
    );

    return new TransactionHandle<Agent>(txHash, this.sdk.chain, async () => {
      this.registrationFile.walletAddress = undefined;
      this.registrationFile.walletChainId = undefined;
      this.touch();
      return this;
    });
  }

  toJSON(): RegistrationFile {
    return { ...this.registrationFile };
  }

  private touch(): this {
    this.registrationFile.updatedAt = Math.floor(Date.now() / 1000);
    return this;
  }
}
