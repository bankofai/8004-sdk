#!/usr/bin/env python3
"""
Check Upgradeable contract events on TRON.

Events:
- IdentityRegistryUpgradeable: Registered
- ValidationRegistryUpgradeable: ValidationRequest, ValidationResponse
- ReputationRegistryUpgradeable: NewFeedback

Usage:
  python scripts/check_upgradeable_events.py --from-block 64698000 --to-block 64699000
  python scripts/check_upgradeable_events.py --tx 0x...
  python scripts/check_upgradeable_events.py --agent-id 2
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

sdk_env = ROOT / ".env"
agg_env = ROOT.parent / "tron-8004-aggregator" / ".env"
if sdk_env.exists():
    load_dotenv(sdk_env)
elif agg_env.exists():
    load_dotenv(agg_env)
else:
    load_dotenv()

from tronpy import Tron  # noqa: E402
from tronpy.providers import HTTPProvider  # noqa: E402
from sdk.chain_utils import fetch_event_logs, normalize_hash  # noqa: E402


def _parse_args():
    parser = argparse.ArgumentParser(description="Check Upgradeable contract events")
    parser.add_argument("--from-block", type=int, default=None)
    parser.add_argument("--to-block", type=int, default=None)
    parser.add_argument("--agent-id", type=str, default=None)
    parser.add_argument("--tx", type=str, default=None, help="Filter by transaction id")
    return parser.parse_args()


def _filter_logs(logs, agent_id=None, tx_id=None):
    filtered = []
    tx_norm = normalize_hash(tx_id) if tx_id else None
    for log in logs:
        if tx_norm:
            log_tx = normalize_hash(log.get("transaction_id") or log.get("txID"))
            if log_tx and log_tx != tx_norm:
                continue
        args = log.get("result") or log.get("event_result") or log.get("data") or {}
        if agent_id is not None:
            log_agent = args.get("agentId") or args.get("tokenId")
            if str(log_agent) != str(agent_id):
                continue
        filtered.append(log)
    return filtered


def _print_logs(title, logs):
    print(f"{title} count={len(logs)}")
    for log in logs:
        args = log.get("result") or log.get("event_result") or log.get("data") or {}
        print(
            {
                "block": log.get("block_number"),
                "tx": log.get("transaction_id") or log.get("txID"),
                "args": args,
            }
        )


def main() -> int:
    args = _parse_args()

    rpc_url = os.getenv("TRON_RPC_URL", "https://nile.trongrid.io")
    identity_registry = os.getenv("IDENTITY_REGISTRY")
    validation_registry = os.getenv("VALIDATION_REGISTRY")
    reputation_registry = os.getenv("REPUTATION_REGISTRY")

    client = Tron(provider=HTTPProvider(rpc_url))
    if args.to_block is None:
        args.to_block = client.get_latest_block_number()
    if args.from_block is None:
        args.from_block = max(args.to_block - 500, 0)

    # Identity: Registered
    logs = fetch_event_logs(
        client=client,
        contract_address=identity_registry,
        event_name="Registered",
        from_block=args.from_block,
        to_block=args.to_block,
        rpc_url=rpc_url,
    )
    logs = _filter_logs(logs, agent_id=args.agent_id, tx_id=args.tx)
    _print_logs("Identity.Registered", logs)

    # Validation: Request + Response
    logs = fetch_event_logs(
        client=client,
        contract_address=validation_registry,
        event_name="ValidationRequest",
        from_block=args.from_block,
        to_block=args.to_block,
        rpc_url=rpc_url,
    )
    logs = _filter_logs(logs, agent_id=args.agent_id, tx_id=args.tx)
    _print_logs("Validation.ValidationRequest", logs)

    logs = fetch_event_logs(
        client=client,
        contract_address=validation_registry,
        event_name="ValidationResponse",
        from_block=args.from_block,
        to_block=args.to_block,
        rpc_url=rpc_url,
    )
    logs = _filter_logs(logs, agent_id=args.agent_id, tx_id=args.tx)
    _print_logs("Validation.ValidationResponse", logs)

    # Reputation: NewFeedback
    logs = fetch_event_logs(
        client=client,
        contract_address=reputation_registry,
        event_name="NewFeedback",
        from_block=args.from_block,
        to_block=args.to_block,
        rpc_url=rpc_url,
    )
    logs = _filter_logs(logs, agent_id=args.agent_id, tx_id=args.tx)
    _print_logs("Reputation.NewFeedback", logs)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
