"""
TRON-8004 SDK Agent Protocol Client Module

Provides an HTTP client compliant with the Agent Protocol standard.

Agent Protocol is an open standard defining common interfaces for AI Agents:
- Create Task (Task)
- Execute Step (Step)
- Get Results

Classes:
    AgentProtocolClient: Standard Agent Protocol Client

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
    Agent Protocol Standard Client.

    Implements core interfaces of Agent Protocol specification:
    - POST /ap/v1/agent/tasks: Create task
    - POST /ap/v1/agent/tasks/{task_id}/steps: Execute step

    Attributes:
        base_url: Agent service base URL
        timeout: HTTP request timeout

    Args:
        base_url: Agent service base URL (e.g., https://agent.example.com)
        timeout: HTTP request timeout (seconds), default 10.0

    Example:
        >>> client = AgentProtocolClient(
        ...     base_url="https://agent.example.com",
        ...     timeout=30.0,
        ... )
        >>> task = client.create_task()
        >>> result = client.execute_step(task["task_id"], '{"action": "quote"}')

    Note:
        Agent Protocol is an open standard for AI Agent interfaces.
        See more at: https://agentprotocol.ai/
    """

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        """
        Initialize Agent Protocol Client.

        Args:
            base_url: Agent service base URL (e.g., https://agent.example.com)
            timeout: HTTP request timeout (seconds)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def create_task(self, input_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new task.

        Sends a task creation request to the Agent and retrieves a task ID.

        Args:
            input_text: Optional initial input text

        Returns:
            Task information dictionary, containing task_id, etc.

        Raises:
            httpx.HTTPStatusError: HTTP request failed
            httpx.TimeoutException: Request timed out

        Example:
            >>> task = client.create_task()
            >>> print(task["task_id"])
            'abc123-...'
            >>>
            >>> # With initial input
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
        Execute a task step.

        Sends an execution request to a specific task and retrieves the step result.

        Args:
            task_id: Task ID (obtained from create_task)
            input_text: Step input text (usually a JSON string)

        Returns:
            Step result dictionary, containing output, status, etc.

        Raises:
            httpx.HTTPStatusError: HTTP request failed
            httpx.TimeoutException: Request timed out

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
        One-click run: Create task and execute.

        Convenience method that automatically creates a task and executes a single step.

        Args:
            input_payload: Input data dictionary, will be serialized to JSON

        Returns:
            Step execution result

        Raises:
            ValueError: Task creation failed (missing task_id)
            httpx.HTTPStatusError: HTTP request failed

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
            This method is suitable for simple single-step tasks.
            For complex multi-step tasks, call create_task and execute_step separately.
        """
        # Create task
        task = self.create_task()
        task_id = task.get("task_id")
        if not task_id:
            raise ValueError("AGENT_TASK_ID_MISSING")

        # Serialize input and execute
        input_text = json.dumps(input_payload, ensure_ascii=False)
        return self.execute_step(task_id, input_text)
