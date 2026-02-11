import type { TxMined, TxWaitOptions } from "../models/types.js";

export interface ChainAdapter {
  waitForTransaction(txHash: string, opts?: TxWaitOptions): Promise<unknown>;
}

export class TransactionHandle<T> {
  constructor(
    readonly txHash: string,
    private readonly chain: ChainAdapter,
    private readonly computeResult: (receipt: unknown) => Promise<T> | T,
  ) {}

  async waitConfirmed(opts: TxWaitOptions = {}): Promise<TxMined<T>> {
    const receipt = await this.chain.waitForTransaction(this.txHash, opts);
    const result = await this.computeResult(receipt);
    return { receipt, result };
  }
}
