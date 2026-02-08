#!/usr/bin/env python3
"""
Hello World agent test for Upgradeable contracts.

Steps:
1) Register agent (tokenURI)
2) Validation request + response (requires validator key)
3) Reputation feedback (validator acts as client)
4) Read back status + feedback

Requires environment variables (example from ../tron-8004-aggregator/.env):
  TRON_RPC_URL
  TRON_NETWORK
  IDENTITY_REGISTRY
  VALIDATION_REGISTRY
  REPUTATION_REGISTRY
  TRON_FEE_LIMIT (optional)
  MARKET_AGENT_PRIVATE_KEY
  VALIDATOR_PRIVATE_KEY
"""

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

# Prefer SDK .env, fallback to aggregator .env, then process env
sdk_env = ROOT / ".env"
agg_env = ROOT.parent / "tron-8004-aggregator" / ".env"
if sdk_env.exists():
    load_dotenv(sdk_env)
elif agg_env.exists():
    load_dotenv(agg_env)
else:
    load_dotenv()

from sdk import AgentSDK  # noqa: E402
from sdk.chain_utils import fetch_event_logs, normalize_hash  # noqa: E402


def _get_block_number(tx_info: dict) -> int | None:
    return (
        tx_info.get("blockNumber")
        or tx_info.get("block_number")
        or tx_info.get("blockNumber".lower())
    )


def _get_agent_id_from_register_tx(
    rpc_url: str,
    contract_address: str,
    tx_id: str,
    retries: int = 12,
    wait_sec: float = 5.0,
) -> int | None:
    try:
        from tronpy import Tron
        from tronpy.providers import HTTPProvider
    except Exception:
        return None

    client = Tron(provider=HTTPProvider(rpc_url))
    target = normalize_hash(tx_id)

    for _ in range(retries):
        tx_info = client.get_transaction_info(tx_id)
        # Prefer contractResult (return value of register)
        contract_result = tx_info.get("contractResult") or tx_info.get("contract_result")
        if isinstance(contract_result, list) and contract_result:
            try:
                return int(contract_result[0], 16)
            except Exception:
                pass
        block_number = _get_block_number(tx_info)
        if block_number is None:
            time.sleep(wait_sec)
            continue

        from_block = max(int(block_number) - 1, 0)
        to_block = int(block_number) + 1
        logs = fetch_event_logs(
            client=client,
            contract_address=contract_address,
            event_name="Registered",
            from_block=from_block,
            to_block=to_block,
            rpc_url=rpc_url,
        )
        # Try to match by tx id first
        for log in logs:
            log_tx = normalize_hash(log.get("transaction_id") or log.get("txID"))
            if log_tx and log_tx != target:
                continue
            args = log.get("result") or log.get("event_result") or log.get("data") or {}
            agent_id = args.get("agentId") or args.get("tokenId")
            if agent_id is not None:
                return int(agent_id)

        # If no tx match but only one log, use it
        if len(logs) == 1:
            args = logs[0].get("result") or logs[0].get("event_result") or logs[0].get("data") or {}
            agent_id = args.get("agentId") or args.get("tokenId")
            if agent_id is not None:
                return int(agent_id)

        time.sleep(wait_sec)
    return None


def _normalize_network(value: str) -> str:
    if value.startswith("tron:"):
        return value
    return f"tron:{value}"


def main() -> int:
    rpc_url = os.getenv("TRON_RPC_URL", "https://nile.trongrid.io")
    network = _normalize_network(os.getenv("TRON_NETWORK", "nile"))
    fee_limit = int(os.getenv("TRON_FEE_LIMIT", "200000000"))

    identity_registry = os.getenv("IDENTITY_REGISTRY")
    validation_registry = os.getenv("VALIDATION_REGISTRY")
    reputation_registry = os.getenv("REPUTATION_REGISTRY")

    abi_root = ROOT.parent / "erc-8004-contracts" / "abis"
    identity_abi = os.getenv("IDENTITY_REGISTRY_ABI_PATH") or str(abi_root / "IdentityRegistry.json")
    validation_abi = os.getenv("VALIDATION_REGISTRY_ABI_PATH") or str(abi_root / "ValidationRegistry.json")
    reputation_abi = os.getenv("REPUTATION_REGISTRY_ABI_PATH") or str(abi_root / "ReputationRegistry.json")

    owner_pk = os.getenv("MARKET_AGENT_PRIVATE_KEY") or os.getenv("TRON_PRIVATE_KEY")
    validator_pk = os.getenv("VALIDATOR_PRIVATE_KEY")

    if not owner_pk:
        print("ERROR: MARKET_AGENT_PRIVATE_KEY (or TRON_PRIVATE_KEY) is required")
        return 1
    if not validator_pk:
        print("ERROR: VALIDATOR_PRIVATE_KEY is required")
        return 1

    owner_sdk = AgentSDK(
        private_key=owner_pk,
        rpc_url=rpc_url,
        network=network,
        identity_registry=identity_registry,
        validation_registry=validation_registry,
        reputation_registry=reputation_registry,
        identity_registry_abi_path=identity_abi,
        validation_registry_abi_path=validation_abi,
        reputation_registry_abi_path=reputation_abi,
        fee_limit=fee_limit,
    )
    validator_sdk = AgentSDK(
        private_key=validator_pk,
        rpc_url=rpc_url,
        network=network,
        identity_registry=identity_registry,
        validation_registry=validation_registry,
        reputation_registry=reputation_registry,
        identity_registry_abi_path=identity_abi,
        validation_registry_abi_path=validation_abi,
        reputation_registry_abi_path=reputation_abi,
        fee_limit=fee_limit,
    )

    owner_addr = owner_sdk.address
    validator_addr = validator_sdk.address
    print("Owner:", owner_addr)
    print("Validator:", validator_addr)
    if owner_addr == validator_addr:
        print("ERROR: owner and validator must be different")
        return 1

    # 1) Register
    token_uri = f"https://example.com/hello-world-{int(time.time())}.json"
    reg_tx = owner_sdk.register_agent(token_uri=token_uri, metadata=None)
    print("register tx=", reg_tx)
    time.sleep(8)
    agent_id = _get_agent_id_from_register_tx(rpc_url, identity_registry, reg_tx)
    if not agent_id:
        print("ERROR: failed to resolve agent_id from Registered event")
        return 1
    print("agent_id=", agent_id)
    print("tokenURI=", owner_sdk.get_agent_uri(agent_id))

    # 2) Validation
    request_uri = f"https://example.com/request-{int(time.time())}.json"
    request_data = f'{{"hello":"world","ts":{int(time.time())}}}'
    request_hash = owner_sdk.compute_request_hash(request_data)
    vreq_tx = owner_sdk.validation_request(
        validator_addr=validator_addr,
        agent_id=agent_id,
        request_uri=request_uri,
        request_hash=request_hash,
    )
    print("validation_request tx=", vreq_tx)
    time.sleep(6)
    vres_tx = validator_sdk.validation_response(
        request_hash=request_hash,
        response=95,
        response_uri="https://example.com/response.json",
        tag="hello-world",
    )
    print("validation_response tx=", vres_tx)
    time.sleep(6)
    status = owner_sdk.get_validation_status(request_hash)
    print("validation_status=", status)
    if int(status.get("response", 0)) != 95:
        print("ERROR: validation response mismatch")
        return 1

    # 3) Reputation
    rep_tx = validator_sdk.submit_reputation(
        agent_id=agent_id,
        value=88,
        value_decimals=0,
        tag1="hello",
        tag2="world",
        endpoint="/hello",
        feedback_uri="https://example.com/feedback.json",
    )
    print("reputation giveFeedback tx=", rep_tx)
    time.sleep(6)
    summary = validator_sdk.get_feedback_summary(agent_id, client_addresses=[validator_addr])
    print("feedback_summary=", summary)
    last_index = validator_sdk.get_last_feedback_index(agent_id, validator_addr)
    print("last_feedback_index=", last_index)
    feedback = validator_sdk.read_feedback(agent_id, validator_addr, last_index)
    print("feedback=", feedback)

    print("✅ Hello World agent test completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
