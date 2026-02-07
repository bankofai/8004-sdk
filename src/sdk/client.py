"""
TRON-8004 SDK Agent Client Module

Provides a smart HTTP client that automatically resolves endpoints from Agent metadata.

Classes:
    AgentClient: Smart Agent HTTP Client

Example:
    >>> from sdk.client import AgentClient
    >>> client = AgentClient(
    ...     metadata=agent_metadata,
    ...     base_url="https://agent.example.com",
    ... )
    >>> response = client.post("quote", {"asset": "TRX/USDT", "amount": 100})

Note:
    - Supports automatic endpoint resolution from Agent metadata
    - Follows A2A protocol URL conventions
    - Supports mock mode for testing
"""

from typing import Dict, Any, Optional

import httpx


class AgentClient:
    """
    Smart Agent HTTP Client.

    Automatically resolves endpoint URLs based on Agent metadata. Supports:
    - Getting base URL from metadata.url
    - Getting A2A endpoint from metadata.endpoints
    - Getting specific capability endpoint from metadata.skills
    - Constructing URL using A2A protocol conventions

    Attributes:
        metadata: Agent metadata dictionary
        base_url: Base URL (lower priority than metadata)

    Args:
        metadata: Agent metadata, usually fetched from Central Service
        base_url: Base URL, fallback for metadata

    Example:
        >>> # Use metadata
        >>> client = AgentClient(metadata={
        ...     "url": "https://agent.example.com",
        ...     "skills": [{"id": "quote", "endpoint": "/custom/quote"}],
        ... })
        >>> client.resolve_url("quote")
        'https://agent.example.com/custom/quote'
        >>>
        >>> # Use base URL
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
        Initialize Agent Client.

        Args:
            metadata: Agent metadata dictionary, containing url, endpoints, skills, etc.
            base_url: Base URL, used when no URL is in metadata
        """
        self.metadata = metadata or {}
        self.base_url = (base_url or "").rstrip("/")

    def resolve_url(self, capability: str) -> str:
        """
        Resolve the complete URL for a capability/skill.

        Resolution priority:
        1. Check mock mode
        2. Get base URL from metadata.url or base_url
        3. Find A2A endpoint from metadata.endpoints
        4. Find specific capability endpoint from metadata.skills
        5. Use A2A protocol convention: {base_url}/a2a/{capability}

        Args:
            capability: Capability/Skill name (e.g., 'quote', 'execute')

        Returns:
            Complete endpoint URL

        Raises:
            ValueError: Base URL not found

        Example:
            >>> client = AgentClient(base_url="https://agent.example.com")
            >>> client.resolve_url("quote")
            'https://agent.example.com/a2a/quote'
        """
        # 0. Check Mock Mode
        if self.base_url == "mock":
            return "mock"

        # 1. Get Base URL
        base_url = self.metadata.get("url") or self.base_url
        if not base_url:
            # Try to get A2A endpoint from endpoints
            for endpoint in self.metadata.get("endpoints", []):
                if endpoint.get("name", "").lower() == "a2a":
                    base_url = endpoint.get("endpoint", "")
                    break

        if not base_url:
            raise ValueError(f"No Base URL found for agent to capability '{capability}'")

        # 2. Check if specific endpoint exists in skills
        skills = self.metadata.get("skills", [])
        if skills:
            skill = next((s for s in skills if s.get("id") == capability), None)
            if skill:
                endpoint = skill.get("endpoint") or skill.get("path")
                if endpoint:
                    # Absolute URL
                    if endpoint.startswith("http://") or endpoint.startswith("https://"):
                        return endpoint
                    # Relative path
                    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        # 3. Use A2A protocol convention
        return f"{base_url.rstrip('/')}/a2a/{capability}"

    def post(
        self,
        capability: str,
        json_data: Dict[str, Any],
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Send POST request to specific capability endpoint.

        Args:
            capability: Capability/Skill name
            json_data: Request body JSON data
            timeout: Request timeout (seconds)

        Returns:
            Response JSON data

        Raises:
            ValueError: URL resolution failed
            httpx.HTTPStatusError: HTTP request failed
            httpx.TimeoutException: Request timed out

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
        Send GET request to specific capability endpoint.

        Args:
            capability: Capability/Skill name
            params: URL query parameters
            timeout: Request timeout (seconds)

        Returns:
            Response JSON data

        Raises:
            ValueError: URL resolution failed
            httpx.HTTPStatusError: HTTP request failed
            httpx.TimeoutException: Request timed out

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
