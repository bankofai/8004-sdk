import json
from typing import Any, Dict, Optional

import httpx


class AgentProtocolClient:
    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def create_task(self, input_text: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if input_text is not None:
            payload["input"] = input_text
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/ap/v1/agent/tasks", json=payload)
            resp.raise_for_status()
            return resp.json()

    def execute_step(self, task_id: str, input_text: Optional[str] = None) -> Dict[str, Any]:
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
        task = self.create_task()
        task_id = task.get("task_id")
        if not task_id:
            raise ValueError("AGENT_TASK_ID_MISSING")
        input_text = json.dumps(input_payload, ensure_ascii=False)
        return self.execute_step(task_id, input_text)
