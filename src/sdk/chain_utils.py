from __future__ import annotations

import os
from typing import Optional

import httpx


def normalize_hash(value: Optional[str]) -> str:
    if not value:
        return ""
    cleaned = value.lower()
    if cleaned.startswith("0x"):
        cleaned = cleaned[2:]
    return cleaned


def load_request_data(request_uri: str) -> str:
    if request_uri.startswith("file://"):
        path = request_uri.replace("file://", "", 1)
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    if request_uri.startswith("ipfs://"):
        cid = request_uri.replace("ipfs://", "", 1)
        gateway = os.getenv("IPFS_GATEWAY_URL", "https://ipfs.io/ipfs")
        url = f"{gateway.rstrip('/')}/{cid}"
        with httpx.Client(timeout=10) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text
    if request_uri.startswith("http://") or request_uri.startswith("https://"):
        with httpx.Client(timeout=10) as client:
            response = client.get(request_uri)
            response.raise_for_status()
            return response.text
    return request_uri


def fetch_event_logs(
    client,
    contract_address: str,
    event_name: str,
    from_block: int,
    to_block: int,
    rpc_url: Optional[str] = None,
) -> list[dict]:
    contract = client.get_contract(contract_address)
    event = getattr(contract.events, event_name, None)
    if event and hasattr(event, "get_logs"):
        try:
            return event.get_logs(from_block=from_block, to_block=to_block)
        except Exception:
            pass
    if hasattr(client, "get_event_result"):
        try:
            return client.get_event_result(
                contract_address=contract_address,
                event_name=event_name,
                from_block=from_block,
                to_block=to_block,
                only_confirmed=True,
                limit=200,
            )
        except Exception:
            pass
    if rpc_url:
        return fetch_trongrid_events(rpc_url, contract_address, event_name, from_block, to_block)
    return []


def fetch_trongrid_events(
    rpc_url: str,
    contract_address: str,
    event_name: str,
    from_block: int,
    to_block: int,
) -> list[dict]:
    base = rpc_url.rstrip("/")
    url = f"{base}/v1/contracts/{contract_address}/events"
    params = {
        "event_name": event_name,
        "only_confirmed": "true",
        "limit": 200,
    }
    items: list[dict] = []
    while True:
        resp = httpx.get(url, params=params, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        batch = payload.get("data") or []
        items.extend(batch)
        fingerprint = (payload.get("meta") or {}).get("fingerprint")
        if not fingerprint:
            break
        params["fingerprint"] = fingerprint
    if from_block or to_block:
        filtered = []
        for item in items:
            block = item.get("block_number")
            if block is None:
                filtered.append(item)
                continue
            if block < from_block:
                continue
            if block > to_block:
                continue
            filtered.append(item)
        return filtered
    return items
