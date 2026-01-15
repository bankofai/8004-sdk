"""
TRC-8004 SDK Agent 客户端模块

提供智能 HTTP 客户端，自动解析 Agent 元数据中的端点。

Classes:
    AgentClient: 智能 Agent HTTP 客户端

Example:
    >>> from sdk.client import AgentClient
    >>> client = AgentClient(
    ...     metadata=agent_metadata,
    ...     base_url="https://agent.example.com",
    ... )
    >>> response = client.post("quote", {"asset": "TRX/USDT", "amount": 100})

Note:
    - 支持从 Agent 元数据自动解析端点
    - 遵循 A2A 协议的 URL 约定
    - 支持 mock 模式用于测试
"""

from typing import Dict, Any, Optional

import httpx


class AgentClient:
    """
    智能 Agent HTTP 客户端。

    根据 Agent 元数据自动解析端点 URL，支持：
    - 从 metadata.url 获取基础 URL
    - 从 metadata.endpoints 获取 A2A 端点
    - 从 metadata.skills 获取特定能力的端点
    - 使用 A2A 协议约定构造 URL

    Attributes:
        metadata: Agent 元数据字典
        base_url: 基础 URL（优先级低于 metadata）

    Args:
        metadata: Agent 元数据，通常从 Central Service 获取
        base_url: 基础 URL，作为 metadata 的回退

    Example:
        >>> # 使用元数据
        >>> client = AgentClient(metadata={
        ...     "url": "https://agent.example.com",
        ...     "skills": [{"id": "quote", "endpoint": "/custom/quote"}],
        ... })
        >>> client.resolve_url("quote")
        'https://agent.example.com/custom/quote'
        >>>
        >>> # 使用基础 URL
        >>> client = AgentClient(base_url="https://agent.example.com")
        >>> client.resolve_url("execute")
        'https://agent.example.com/a2a/execute'
    """

    def __init__(
        self,
        metadata: Optional[Dict[str, Any]] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """
        初始化 Agent 客户端。

        Args:
            metadata: Agent 元数据字典，包含 url、endpoints、skills 等
            base_url: 基础 URL，当 metadata 中没有 URL 时使用
        """
        self.metadata = metadata or {}
        self.base_url = (base_url or "").rstrip("/")

    def resolve_url(self, capability: str) -> str:
        """
        解析能力/技能对应的完整 URL。

        解析优先级：
        1. 检查 mock 模式
        2. 从 metadata.url 或 base_url 获取基础 URL
        3. 从 metadata.endpoints 查找 A2A 端点
        4. 从 metadata.skills 查找特定能力的端点
        5. 使用 A2A 协议约定：{base_url}/a2a/{capability}

        Args:
            capability: 能力/技能名称（如 'quote', 'execute'）

        Returns:
            完整的端点 URL

        Raises:
            ValueError: 无法找到基础 URL

        Example:
            >>> client = AgentClient(base_url="https://agent.example.com")
            >>> client.resolve_url("quote")
            'https://agent.example.com/a2a/quote'
        """
        # 0. 检查 Mock 模式
        if self.base_url == "mock":
            return "mock"

        # 1. 获取基础 URL
        base_url = self.metadata.get("url") or self.base_url
        if not base_url:
            # 尝试从 endpoints 获取 A2A 端点
            for endpoint in self.metadata.get("endpoints", []):
                if endpoint.get("name", "").lower() == "a2a":
                    base_url = endpoint.get("endpoint", "")
                    break

        if not base_url:
            raise ValueError(f"No Base URL found for agent to capability '{capability}'")

        # 2. 检查 skills 中是否有特定端点
        skills = self.metadata.get("skills", [])
        if skills:
            skill = next((s for s in skills if s.get("id") == capability), None)
            if skill:
                endpoint = skill.get("endpoint") or skill.get("path")
                if endpoint:
                    # 绝对 URL
                    if endpoint.startswith("http://") or endpoint.startswith("https://"):
                        return endpoint
                    # 相对路径
                    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        # 3. 使用 A2A 协议约定
        return f"{base_url.rstrip('/')}/a2a/{capability}"

    def post(
        self,
        capability: str,
        json_data: Dict[str, Any],
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """
        向指定能力端点发送 POST 请求。

        Args:
            capability: 能力/技能名称
            json_data: 请求体 JSON 数据
            timeout: 请求超时时间（秒）

        Returns:
            响应 JSON 数据

        Raises:
            ValueError: 无法解析 URL
            httpx.HTTPStatusError: HTTP 请求失败
            httpx.TimeoutException: 请求超时

        Example:
            >>> response = client.post("quote", {
            ...     "asset": "TRX/USDT",
            ...     "amount": 100,
            ... })
        """
        url = self.resolve_url(capability)
        if url == "mock":
            return {"mock": True}

        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=json_data)
            response.raise_for_status()
            return response.json()

    def get(
        self,
        capability: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """
        向指定能力端点发送 GET 请求。

        Args:
            capability: 能力/技能名称
            params: URL 查询参数
            timeout: 请求超时时间（秒）

        Returns:
            响应 JSON 数据

        Raises:
            ValueError: 无法解析 URL
            httpx.HTTPStatusError: HTTP 请求失败
            httpx.TimeoutException: 请求超时

        Example:
            >>> response = client.get("status", params={"order_id": "123"})
        """
        url = self.resolve_url(capability)
        if url == "mock":
            return {"mock": True}

        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
