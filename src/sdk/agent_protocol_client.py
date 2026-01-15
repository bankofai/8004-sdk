"""
TRC-8004 SDK Agent Protocol 客户端模块

提供符合 Agent Protocol 标准的 HTTP 客户端。

Agent Protocol 是一个开放标准，定义了 AI Agent 的通用接口：
- 创建任务 (Task)
- 执行步骤 (Step)
- 获取结果

Classes:
    AgentProtocolClient: Agent Protocol 标准客户端

Reference:
    https://agentprotocol.ai/

Example:
    >>> from sdk.agent_protocol_client import AgentProtocolClient
    >>> client = AgentProtocolClient(base_url="https://agent.example.com")
    >>> result = client.run({"skill": "quote", "params": {...}})
"""

import json
from typing import Any, Dict, Optional

import httpx


class AgentProtocolClient:
    """
    Agent Protocol 标准客户端。

    实现 Agent Protocol 规范的核心接口：
    - POST /ap/v1/agent/tasks: 创建任务
    - POST /ap/v1/agent/tasks/{task_id}/steps: 执行步骤

    Attributes:
        base_url: Agent 服务基础 URL
        timeout: HTTP 请求超时时间

    Args:
        base_url: Agent 服务基础 URL
        timeout: HTTP 请求超时时间（秒），默认 10.0

    Example:
        >>> client = AgentProtocolClient(
        ...     base_url="https://agent.example.com",
        ...     timeout=30.0,
        ... )
        >>> task = client.create_task()
        >>> result = client.execute_step(task["task_id"], '{"action": "quote"}')

    Note:
        Agent Protocol 是一个开放标准，旨在提供 AI Agent 的通用接口。
        更多信息请参考: https://agentprotocol.ai/
    """

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        """
        初始化 Agent Protocol 客户端。

        Args:
            base_url: Agent 服务基础 URL（如 https://agent.example.com）
            timeout: HTTP 请求超时时间（秒）
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def create_task(self, input_text: Optional[str] = None) -> Dict[str, Any]:
        """
        创建新任务。

        向 Agent 发送创建任务请求，获取任务 ID。

        Args:
            input_text: 可选的初始输入文本

        Returns:
            任务信息字典，包含 task_id 等字段

        Raises:
            httpx.HTTPStatusError: HTTP 请求失败
            httpx.TimeoutException: 请求超时

        Example:
            >>> task = client.create_task()
            >>> print(task["task_id"])
            'abc123-...'
            >>>
            >>> # 带初始输入
            >>> task = client.create_task(input_text="Hello")
        """
        payload: Dict[str, Any] = {}
        if input_text is not None:
            payload["input"] = input_text

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/ap/v1/agent/tasks", json=payload)
            resp.raise_for_status()
            return resp.json()

    def execute_step(
        self,
        task_id: str,
        input_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行任务步骤。

        向指定任务发送执行请求，获取步骤结果。

        Args:
            task_id: 任务 ID（从 create_task 获取）
            input_text: 步骤输入文本（通常是 JSON 字符串）

        Returns:
            步骤结果字典，包含 output、status 等字段

        Raises:
            httpx.HTTPStatusError: HTTP 请求失败
            httpx.TimeoutException: 请求超时

        Example:
            >>> result = client.execute_step(
            ...     task_id="abc123",
            ...     input_text='{"action": "quote", "params": {...}}',
            ... )
            >>> print(result["output"])
        """
        payload: Dict[str, Any] = {}
        if input_text is not None:
            payload["input"] = input_text

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}/ap/v1/agent/tasks/{task_id}/steps",
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

    def run(self, input_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        一键运行：创建任务并执行。

        便捷方法，自动创建任务并执行一个步骤。

        Args:
            input_payload: 输入数据字典，将被序列化为 JSON

        Returns:
            步骤执行结果

        Raises:
            ValueError: 任务创建失败（无 task_id）
            httpx.HTTPStatusError: HTTP 请求失败

        Example:
            >>> result = client.run({
            ...     "skill": "market_order",
            ...     "params": {
            ...         "asset": "TRX/USDT",
            ...         "amount": 100,
            ...     },
            ... })
            >>> print(result["output"])

        Note:
            此方法适用于简单的单步骤任务。
            对于复杂的多步骤任务，请分别调用 create_task 和 execute_step。
        """
        # 创建任务
        task = self.create_task()
        task_id = task.get("task_id")
        if not task_id:
            raise ValueError("AGENT_TASK_ID_MISSING")

        # 序列化输入并执行
        input_text = json.dumps(input_payload, ensure_ascii=False)
        return self.execute_step(task_id, input_text)
