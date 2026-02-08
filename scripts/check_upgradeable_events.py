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
from eth_utils import keccak  # noqa: E402
from eth_abi import decode as abi_decode  # noqa: E402


def _load_abi(path: str):
    try:
        import json

        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict) and "abi" in data:
            return data["abi"]
        return data
    except Exception:
        return None


def _event_signature(event_abi: dict) -> str:
    types = ",".join(inp["type"] for inp in event_abi.get("inputs", []))
    return f"{event_abi.get('name')}({types})"


def _topic0(event_abi: dict) -> str:
    sig = _event_signature(event_abi)
    return keccak(text=sig).hex()


def _decode_topic_value(value_hex: str, typ: str):
    raw = bytes.fromhex(value_hex)
    if typ == "address":
        return "0x" + raw[-20:].hex()
    if typ.startswith("uint") or typ.startswith("int"):
        return int.from_bytes(raw, byteorder="big", signed=typ.startswith("int"))
    if typ == "bytes32":
        return "0x" + raw.hex()
    return "0x" + raw.hex()


def _decode_log_with_abi(log: dict, event_abi: dict) -> dict:
    topics = [t.lower() for t in (log.get("topics") or [])]
    data_hex = (log.get("data") or "") or ""
    data_bytes = bytes.fromhex(data_hex) if data_hex else b""

    indexed_inputs = [i for i in event_abi["inputs"] if i.get("indexed")]
    non_indexed_inputs = [i for i in event_abi["inputs"] if not i.get("indexed")]

    decoded = {}
    # indexed params are in topics[1..]
    for idx, inp in enumerate(indexed_inputs):
        if idx + 1 >= len(topics):
            continue
        decoded[inp["name"]] = _decode_topic_value(topics[idx + 1], inp["type"])

    if non_indexed_inputs:
        types = [i["type"] for i in non_indexed_inputs]
        values = abi_decode(types, data_bytes)
        for inp, val in zip(non_indexed_inputs, values):
            if isinstance(val, bytes):
                decoded[inp["name"]] = "0x" + val.hex()
            else:
                decoded[inp["name"]] = val
    return decoded


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
    abi_root = ROOT.parent / "erc-8004-contracts" / "abis"
    identity_abi = os.getenv("IDENTITY_REGISTRY_ABI_PATH") or str(abi_root / "IdentityRegistry.json")
    validation_abi = os.getenv("VALIDATION_REGISTRY_ABI_PATH") or str(abi_root / "ValidationRegistry.json")
    reputation_abi = os.getenv("REPUTATION_REGISTRY_ABI_PATH") or str(abi_root / "ReputationRegistry.json")

    abi_map = {
        identity_registry: _load_abi(identity_abi),
        validation_registry: _load_abi(validation_abi),
        reputation_registry: _load_abi(reputation_abi),
    }

    def fetch_with_abi(contract_address: str, event_name: str):
        contract = client.get_contract(contract_address)
        abi = abi_map.get(contract_address)
        if abi:
            contract.abi = abi
        event = getattr(contract.events, event_name, None)
        if event and hasattr(event, "get_logs"):
            return event.get_logs(from_block=args.from_block, to_block=args.to_block)
        return []

    client = Tron(provider=HTTPProvider(rpc_url))
    if args.to_block is None:
        args.to_block = client.get_latest_block_number()
    if args.from_block is None:
        args.from_block = max(args.to_block - 500, 0)

    # If tx is provided, dump raw logs from tx receipt for inspection
    if args.tx:
        info = client.get_transaction_info(args.tx)
        logs = info.get("log") or []
        print(f"Tx logs count={len(logs)}")
        for log in logs:
            print({"address": log.get("address"), "topics": log.get("topics"), "data": log.get("data")})

        # Try to decode logs using ABI signatures
        abi_events = {}
        for addr, abi in abi_map.items():
            if not abi:
                continue
            for item in abi:
                if item.get("type") != "event":
                    continue
                abi_events[_topic0(item)] = item

        print("Decoded events:")
        for log in logs:
            topics = log.get("topics") or []
            if not topics:
                continue
            t0 = topics[0].lower()
            event_abi = abi_events.get(t0)
            if not event_abi:
                continue
            decoded = _decode_log_with_abi(log, event_abi)
            print({"event": event_abi.get("name"), "args": decoded})

    # Identity: Registered
    logs = fetch_with_abi(identity_registry, "Registered")
    if not logs:
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
    logs = fetch_with_abi(validation_registry, "ValidationRequest")
    if not logs:
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

    logs = fetch_with_abi(validation_registry, "ValidationResponse")
    if not logs:
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
    logs = fetch_with_abi(reputation_registry, "NewFeedback")
    if not logs:
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
