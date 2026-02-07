"""
TRON-8004 SDK Chain Utilities Module

Provides utility functions for blockchain data loading and event listening.

Functions:
    normalize_hash: Normalize hash strings
    load_request_data: Load request data from URI
    fetch_event_logs: Fetch contract event logs
    fetch_trongrid_events: Fetch events from TronGrid API

Supported URI Schemes:
    - file://: Local file
    - ipfs://: IPFS content (via gateway)
    - http://, https://: HTTP(S) URL

Example:
    >>> from sdk.chain_utils import load_request_data, normalize_hash
    >>> data = load_request_data("ipfs://QmXxx...")
    >>> hash_str = normalize_hash("0xABC123")  # -> "abc123"

Environment Variables:
    IPFS_GATEWAY_URL: IPFS gateway URL, default https://ipfs.io/ipfs
"""

from __future__ import annotations

import os
from typing import Optional, Any

import httpx


def normalize_hash(value: Optional[str]) -> str:
    """
    Normalize hash string.

    Converts hash to lowercase and removes 0x prefix.

    Args:
        value: Hash string, may have 0x prefix

    Returns:
        Normalized hash string (lowercase, no prefix),
        returns empty string if input is empty

    Example:
        >>> normalize_hash("0xABC123")
        'abc123'
        >>> normalize_hash("DEF456")
        'def456'
        >>> normalize_hash(None)
        ''
    """
    if not value:
        return ""
    cleaned = value.lower()
    if cleaned.startswith("0x"):
        cleaned = cleaned[2:]
    return cleaned


def load_request_data(request_uri: str) -> str:
    """
    Load request data from URI.

    Supports multiple URI protocols:
    - file://: Read from local file system
    - ipfs://: Fetch via IPFS gateway
    - http://, https://: Direct HTTP request

    Args:
        request_uri: Data URI

    Returns:
        Loaded data content (string)

    Raises:
        FileNotFoundError: Local file does not exist
        httpx.HTTPStatusError: HTTP request failed
        httpx.TimeoutException: Request timed out

    Example:
        >>> # Load from local file
        >>> data = load_request_data("file:///path/to/file.json")
        >>>
        >>> # Load from IPFS
        >>> data = load_request_data("ipfs://QmXxx...")
        >>>
        >>> # Load from HTTP URL
        >>> data = load_request_data("https://example.com/data.json")

    Note:
        - IPFS gateway can be configured via IPFS_GATEWAY_URL environment variable
        - HTTP request timeout is 10 seconds
        - Returns original string if URI matches no known protocol
    """
    # Local file
    if request_uri.startswith("file://"):
        path = request_uri.replace("file://", "", 1)
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    # IPFS content
    if request_uri.startswith("ipfs://"):
        cid = request_uri.replace("ipfs://", "", 1)
        gateway = os.getenv("IPFS_GATEWAY_URL", "https://ipfs.io/ipfs")
        url = f"{gateway.rstrip('/')}/{cid}"
        with httpx.Client(timeout=10) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    # HTTP(S) URL
    if request_uri.startswith("http://") or request_uri.startswith("https://"):
        with httpx.Client(timeout=10) as client:
            response = client.get(request_uri)
            response.raise_for_status()
            return response.text

    # Unknown protocol, return as is
    return request_uri


def fetch_event_logs(
    client: Any,
    contract_address: str,
    event_name: str,
    from_block: int,
    to_block: int,
    rpc_url: Optional[str] = None,
) -> list[dict]:
    """
    Fetch contract event logs.

    Attempts multiple ways to fetch events:
    1. Use contract object's events property
    2. Use client's get_event_result method
    3. Fallback to TronGrid API

    Args:
        client: Blockchain client object (e.g., tronpy.Tron)
        contract_address: Contract address
        event_name: Event name (e.g., "ValidationRequest")
        from_block: Start block number
        to_block: End block number
        rpc_url: RPC URL, used for TronGrid API fallback

    Returns:
        List of event logs, each event is a dictionary

    Example:
        >>> from tronpy import Tron
        >>> client = Tron()
        >>> events = fetch_event_logs(
        ...     client=client,
        ...     contract_address="TValidationRegistry...",
        ...     event_name="ValidationRequest",
        ...     from_block=1000000,
        ...     to_block=1001000,
        ... )
        >>> for event in events:
        ...     print(event["transaction_id"])

    Note:
        - Event format may vary slightly between different fetch methods
        - Specifying rpc_url is recommended to ensure fallback mechanism works
    """
    # Method 1: Use contract's events property
    contract = client.get_contract(contract_address)
    event = getattr(contract.events, event_name, None)
    if event and hasattr(event, "get_logs"):
        try:
            return event.get_logs(from_block=from_block, to_block=to_block)
        except Exception:
            pass

    # Method 2: Use client's get_event_result method
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

    # Method 3: Fallback to TronGrid API
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
    """
    Fetch contract events from TronGrid API.

    Uses TronGrid REST API with pagination,
    and filters by block range.

    Args:
        rpc_url: TronGrid API base URL (e.g., https://api.trongrid.io)
        contract_address: Contract address
        event_name: Event name
        from_block: Start block number (inclusive)
        to_block: End block number (inclusive)

    Returns:
        List of event logs

    Raises:
        httpx.HTTPStatusError: API request failed

    Example:
        >>> events = fetch_trongrid_events(
        ...     rpc_url="https://api.trongrid.io",
        ...     contract_address="TValidationRegistry...",
        ...     event_name="ValidationRequest",
        ...     from_block=1000000,
        ...     to_block=1001000,
        ... )

    Note:
        - Uses pagination to fetch all events (max 200 per page)
        - Block range filtering is done client-side
        - Only returns confirmed events
    """
    base = rpc_url.rstrip("/")
    url = f"{base}/v1/contracts/{contract_address}/events"
    params: dict[str, Any] = {
        "event_name": event_name,
        "only_confirmed": "true",
        "limit": 200,
    }

    items: list[dict] = []

    # Fetch all events with pagination
    while True:
        resp = httpx.get(url, params=params, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        batch = payload.get("data") or []
        items.extend(batch)

        # Check for next page
        fingerprint = (payload.get("meta") or {}).get("fingerprint")
        if not fingerprint:
            break
        params["fingerprint"] = fingerprint

    # Filter by block range
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
