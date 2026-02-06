"""
TRC-8004 SDK 链上工具模块

提供区块链数据加载和事件监听的工具函数。

Functions:
    normalize_hash: 规范化哈希字符串
    load_request_data: 从 URI 加载请求数据
    fetch_event_logs: 获取合约事件日志
    fetch_trongrid_events: 从 TronGrid API 获取事件

Supported URI Schemes:
    - file://: 本地文件
    - ipfs://: IPFS 内容（通过网关）
    - http://, https://: HTTP(S) URL

Example:
    >>> from sdk.chain_utils import load_request_data, normalize_hash
    >>> data = load_request_data("ipfs://QmXxx...")
    >>> hash_str = normalize_hash("0xABC123")  # -> "abc123"

Environment Variables:
    IPFS_GATEWAY_URL: IPFS 网关地址，默认 https://ipfs.io/ipfs
"""

from __future__ import annotations

import os
from typing import Optional, Any

import httpx


def normalize_hash(value: Optional[str]) -> str:
    """
    规范化哈希字符串。

    将哈希转换为小写并移除 0x 前缀。

    Args:
        value: 哈希字符串，可带 0x 前缀

    Returns:
        规范化的哈希字符串（小写，无前缀），
        如果输入为空则返回空字符串

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
    从 URI 加载请求数据。

    支持多种 URI 协议：
    - file://: 从本地文件系统读取
    - ipfs://: 通过 IPFS 网关获取
    - http://, https://: 直接 HTTP 请求

    Args:
        request_uri: 数据 URI

    Returns:
        加载的数据内容（字符串）

    Raises:
        FileNotFoundError: 本地文件不存在
        httpx.HTTPStatusError: HTTP 请求失败
        httpx.TimeoutException: 请求超时

    Example:
        >>> # 从本地文件加载
        >>> data = load_request_data("file:///path/to/file.json")
        >>>
        >>> # 从 IPFS 加载
        >>> data = load_request_data("ipfs://QmXxx...")
        >>>
        >>> # 从 HTTP URL 加载
        >>> data = load_request_data("https://example.com/data.json")

    Note:
        - IPFS 网关可通过 IPFS_GATEWAY_URL 环境变量配置
        - HTTP 请求超时时间为 10 秒
        - 如果 URI 不匹配任何已知协议，原样返回
    """
    # 本地文件
    if request_uri.startswith("file://"):
        path = request_uri.replace("file://", "", 1)
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    # IPFS 内容
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

    # 未知协议，原样返回
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
    获取合约事件日志。

    尝试多种方式获取事件：
    1. 使用合约对象的 events 属性
    2. 使用客户端的 get_event_result 方法
    3. 回退到 TronGrid API

    Args:
        client: 区块链客户端对象（如 tronpy.Tron）
        contract_address: 合约地址
        event_name: 事件名称（如 "ValidationRequest"）
        from_block: 起始区块号
        to_block: 结束区块号
        rpc_url: RPC URL，用于 TronGrid API 回退

    Returns:
        事件日志列表，每个事件为字典格式

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
        - 不同的获取方式返回的事件格式可能略有不同
        - 建议指定 rpc_url 以确保回退机制可用
    """
    # 方式 1: 使用合约的 events 属性
    contract = client.get_contract(contract_address)
    event = getattr(contract.events, event_name, None)
    if event and hasattr(event, "get_logs"):
        try:
            return event.get_logs(from_block=from_block, to_block=to_block)
        except Exception:
            pass

    # 方式 2: 使用客户端的 get_event_result 方法
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

    # 方式 3: 回退到 TronGrid API
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
    从 TronGrid API 获取合约事件。

    使用 TronGrid 的 REST API 分页获取事件，
    并按区块范围过滤。

    Args:
        rpc_url: TronGrid API 基础 URL（如 https://api.trongrid.io）
        contract_address: 合约地址
        event_name: 事件名称
        from_block: 起始区块号（包含）
        to_block: 结束区块号（包含）

    Returns:
        事件日志列表

    Raises:
        httpx.HTTPStatusError: API 请求失败

    Example:
        >>> events = fetch_trongrid_events(
        ...     rpc_url="https://api.trongrid.io",
        ...     contract_address="TValidationRegistry...",
        ...     event_name="ValidationRequest",
        ...     from_block=1000000,
        ...     to_block=1001000,
        ... )

    Note:
        - 使用分页获取所有事件（每页最多 200 条）
        - 区块范围过滤在客户端进行
        - 仅返回已确认的事件
    """
    base = rpc_url.rstrip("/")
    url = f"{base}/v1/contracts/{contract_address}/events"
    params: dict[str, Any] = {
        "event_name": event_name,
        "only_confirmed": "true",
        "limit": 200,
    }

    items: list[dict] = []

    # 分页获取所有事件
    while True:
        resp = httpx.get(url, params=params, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        batch = payload.get("data") or []
        items.extend(batch)

        # 检查是否有下一页
        fingerprint = (payload.get("meta") or {}).get("fingerprint")
        if not fingerprint:
            break
        params["fingerprint"] = fingerprint

    # 按区块范围过滤
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
