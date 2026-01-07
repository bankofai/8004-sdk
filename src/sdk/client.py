import httpx
from typing import Dict, Any, Optional

class AgentClient:
    """
    A smart client that resolves endpoints from agent metadata and performs HTTP requests.
    """
    def __init__(self, metadata: Optional[Dict[str, Any]] = None, base_url: Optional[str] = None) -> None:
        self.metadata = metadata or {}
        self.base_url = (base_url or "").rstrip("/")
    
    def resolve_url(self, capability: str) -> str:
        """
        Resolve the full URL for a given capability/skill name (e.g. 'quote', 'execute').
        Using A2A Protocol: Base URL + Convention.
        """
        # 0. Check Mock
        if self.base_url == "mock":
             return "mock"
             
        # 1. Base URL is primary source, fallback to A2A endpoint if provided
        base_url = self.metadata.get("url") or self.base_url
        if not base_url:
            for endpoint in self.metadata.get("endpoints", []):
                if endpoint.get("name", "").lower() == "a2a":
                    base_url = endpoint.get("endpoint", "")
                    break
        if not base_url:
            raise ValueError(f"No Base URL found for agent to capability '{capability}'")
            
        # 2. Verify capability exists in skills (Optional but good validation)
        skills = self.metadata.get("skills", [])
        # If skills list is present, check if capability is listed
        if skills:
            skill = next((s for s in skills if s.get("id") == capability), None)
            if skill:
                endpoint = skill.get("endpoint") or skill.get("path")
                if endpoint:
                    if endpoint.startswith("http://") or endpoint.startswith("https://"):
                        return endpoint
                    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        # 3. Construct URL (generic A2A convention)
        return f"{base_url.rstrip('/')}/a2a/{capability}"

    def post(self, capability: str, json_data: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
        """
        Resolve URL for capability and send POST request.
        """
        url = self.resolve_url(capability)
        if url == "mock":
            return {"mock": True}
            
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=json_data)
            response.raise_for_status()
            return response.json()

    def get(self, capability: str, params: Optional[Dict[str, Any]] = None, timeout: float = 10.0) -> Dict[str, Any]:
        """
        Resolve URL for capability and send GET request.
        """
        url = self.resolve_url(capability)
        if url == "mock":
            return {"mock": True}

        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            return response.json()
